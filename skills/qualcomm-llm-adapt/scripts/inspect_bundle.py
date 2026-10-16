#!/usr/bin/env python3
"""Inventory a model directory or tar without extracting or loading proprietary code."""
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

JSON_LIMIT = 16 * 1024 * 1024
JSON_NAMES = {'genie_config.json', 'config.json', 'metadata.json', 'graph_io_report.json', 'fullgraph_io_report.json', 'bundle_report.json'}


def quantization(tensor):
    q = tensor.get('quantization', {})
    if not isinstance(q, dict):
        return {'unrecognized_metadata': q}
    encoding = q.get('quantizationEncoding')
    value = q.get('scaleOffset', {})
    return {'encoding': encoding, 'scale': value.get('scale', tensor.get('scale')),
            'offset': value.get('offset', tensor.get('offset')), 'axis': q.get('axisScaleOffset'),
            'metadata': q}


def inspect(path, hash_contexts=False):
    docs, files, links, hashes = {}, [], {}, {}
    if path.is_dir():
        for p in sorted(path.rglob('*')):
            name = p.relative_to(path).as_posix()
            if p.is_symlink():
                links[name] = str(p.readlink())
            if not p.is_file():
                continue
            files.append(name)
            if p.name in JSON_NAMES and p.stat().st_size <= JSON_LIMIT:
                docs[name] = json.loads(p.read_text())
            if hash_contexts and p.suffix == '.bin':
                with p.open('rb') as source:
                    hashes[name] = hashlib.file_digest(source, 'sha256').hexdigest()
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            for member in archive:
                if member.issym() or member.islnk():
                    links[member.name] = member.linkname
                if not member.isfile():
                    continue
                files.append(member.name)
                if PurePosixPath(member.name).name in JSON_NAMES and member.size <= JSON_LIMIT:
                    source = archive.extractfile(member)
                    if source:
                        with source:
                            docs[member.name] = json.load(source)
                if hash_contexts and member.name.endswith('.bin'):
                    with archive.extractfile(member) as source:
                        hashes[member.name] = hashlib.file_digest(source, 'sha256').hexdigest()
    else:
        raise ValueError('expected an existing directory or readable tar archive')
    warnings, graphs, context_entries = [], {}, []
    for name, doc in docs.items():
        if not isinstance(doc, dict):
            warnings.append(f'{name}: unsupported report root; expected a JSON object')
            continue
        if PurePosixPath(name).name == 'genie_config.json':
            entries = doc.get('dialog', {}).get('engine', {}).get('model', {}).get('binary', {}).get('ctx-bins', [])
            parent = PurePosixPath(name).parent
            for entry in entries:
                context_entries.append(entry)
                candidate = str(parent / entry)
                # Normalize leading ./ only; do not access arbitrary configured absolute paths.
                if candidate.removeprefix('./') not in {f.removeprefix('./') for f in files}:
                    warnings.append(f'configured context not present as regular packaged file: {entry}')
        graph_list = doc.get('graphs', [])
        if not isinstance(graph_list, list):
            warnings.append(f'{name}: unsupported graphs schema; expected a list')
            continue
        for graph in graph_list:
            if not isinstance(graph, dict):
                warnings.append(f'{name}: unsupported graph entry; expected an object')
                continue
            graph_name = graph.get('graph_name', graph.get('name'))
            if not graph_name:
                continue
            match = re.fullmatch(r'(?:\w+_)?ar(\d+)_cl(\d+)_(\d+)_of_(\d+)', graph_name)
            io = {}
            for key in ('inputs', 'outputs'):
                io[key] = [{'name': t['name'], 'shape': t.get('shape'), 'dtype': t.get('dtype'),
                            'quantization': quantization(t)} for t in graph.get(key, [])]
            inputs = {t['name']: t for t in graph.get('inputs', [])}
            pairs = []
            for output in graph.get('outputs', []):
                if output['name'].startswith(('recurrent_state_', 'conv_state_')) and output['name'].endswith('_out'):
                    input_name = output['name'][:-4] + '_in'
                    if input_name not in inputs:
                        warnings.append(f'{graph_name}: no input for {output["name"]}')
                    else:
                        inp = inputs[input_name]
                        in_shape, out_shape = inp.get('shape'), output.get('shape')
                        same_shape = in_shape == out_shape and in_shape is not None
                        is_conv = input_name.startswith('conv_state_')
                        conv_compatible = bool(
                            is_conv and isinstance(in_shape, list) and isinstance(out_shape, list)
                            and len(in_shape) == len(out_shape) == 4
                            and in_shape[:2] == out_shape[:2] and in_shape[3] == out_shape[3]
                            and isinstance(in_shape[2], int) and isinstance(out_shape[2], int)
                            and out_shape[2] >= in_shape[2] + (int(match.group(1)) if match else 1))
                        if not same_shape and not conv_compatible:
                            warnings.append(f'{graph_name}: state shape mismatch: {input_name} -> {output["name"]}')
                        pairs.append({'input': input_name, 'output': output['name'],
                                      'matching_shape': same_shape,
                                      'conv_tail_shape_compatible': conv_compatible,
                                      'matching_dtype': inp.get('dtype') == output.get('dtype'),
                                      'matching_quantization': quantization(inp) == quantization(output),
                                      'layout_verified': False})
            graphs[graph_name] = {'source_report': name, 'ar_cl_shard_count': list(map(int, match.groups())) if match else None,
                                  **io, 'state_pairs': pairs}
    if links:
        warnings.append('symlinks/hardlinks found: verify targets are included in a standalone handoff')
    if not graphs:
        warnings.append('no supported graph I/O report found; obtain QNN introspection, do not infer layout from filenames')
    if graphs:
        warnings.append('dtype/shape/encoding matches alone do not prove raw-copy safety; layout and lifetime remain unverified')
    return {'path': str(path), 'configured_contexts': context_entries,
            'context_files': [f for f in files if f.endswith('.bin')],
            'tokenizer_files': [f for f in files if PurePosixPath(f).name in {'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'}],
            'lut_files': [f for f in files if PurePosixPath(f).name == 'embedding_weights.raw'],
            'symlinks': links, 'context_sha256': hashes, 'graphs': graphs, 'warnings': warnings,
            'runtime_validation': 'not performed; static inventory only'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--hash-contexts', action='store_true', help='read all context bytes, potentially large')
    args = parser.parse_args()
    try:
        report = inspect(args.bundle, args.hash_contexts)
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        parser.exit(2, f'inspection failed: {error}\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
