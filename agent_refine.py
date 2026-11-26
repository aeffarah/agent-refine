"""Local, aggregate-only diagnostics for OpenCode JSON session exports."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


def analyze(session):
    if not isinstance(session, dict) or not isinstance(session.get('messages'), list):
        raise ValueError('Expected an OpenCode export with a messages array')
    info = session.get('info', {})
    messages = session['messages']
    tokens = Counter()
    finishes = Counter()
    tools = Counter()
    statuses = Counter()
    seen_reads = set()
    read_targets = Counter()
    repeated_reads = identical_reads = writes = compactions = aborted = 0
    uncounted_reasoning = 0
    start_times, end_times, generations = [], [], []
    edit_tools = {'edit', 'write', 'apply_patch', 'multiedit'}
    for message in messages:
        m = message.get('info', {})
        parts = message.get('parts', [])
        time = m.get('time', {})
        if isinstance(time.get('created'), (int, float)):
            start_times.append(time['created'])
        if isinstance(time.get('completed'), (int, float)):
            end_times.append(time['completed'])
        compactions += sum(p.get('type') == 'compaction' for p in parts)
        if m.get('role') != 'assistant':
            continue
        t = m.get('tokens', {})
        for key in ('input', 'output', 'reasoning'):
            tokens[key] += t.get(key, 0) or 0
        finish = m.get('finish')
        is_aborted = m.get('error', {}).get('name') == 'MessageAbortedError'
        aborted += is_aborted
        finishes[finish if finish in {'length', 'stop', 'tool-calls', 'error', 'content-filter'} else ('aborted' if is_aborted else 'other')] += 1
        reasoning_chars = sum(len(p.get('text', '')) for p in parts if p.get('type') == 'reasoning')
        if reasoning_chars and not t.get('reasoning'):
            uncounted_reasoning += reasoning_chars
        seconds = None
        if all(isinstance(time.get(k), (int, float)) for k in ('created', 'completed')):
            seconds = round(max(0, time['completed'] - time['created']) / 1000, 3)
        generations.append({'seconds': seconds, 'finish': finish if finish in {'length', 'stop', 'tool-calls', 'error', 'content-filter'} else ('aborted' if is_aborted else 'other'), 'recorded_reasoning_tokens': t.get('reasoning', 0), 'recorded_output_tokens': t.get('output', 0), 'reasoning_chars': reasoning_chars})
        for p in parts:
            if p.get('type') != 'tool':
                continue
            name = p.get('tool', '')
            state = p.get('state', {})
            status = state.get('status')
            # Avoid leaking custom tool names or tool arguments in reports.
            known = name if name in edit_tools | {'read', 'bash', 'glob', 'grep', 'task', 'todowrite', 'webfetch', 'list'} else 'other'
            tools[known] += 1
            statuses[status if status in {'completed', 'error', 'pending', 'running'} else 'other'] += 1
            if status != 'completed':
                continue
            if name in edit_tools:
                writes += 1
                # An edit might change previously read content; reset duplicate-read tracking.
                seen_reads.clear()
                read_targets.clear()
            if name == 'read':
                target = state.get('input', {}).get('filePath')
                if isinstance(target, str):
                    repeated_reads += read_targets[target] > 0
                    read_targets[target] += 1
                    output = state.get('output')
                    if isinstance(output, str):
                        signature = (target, hashlib.sha256(output.encode()).digest())
                        identical_reads += signature in seen_reads
                        seen_reads.add(signature)
    created = info.get('time', {}).get('created')
    if isinstance(created, (int, float)):
        start_times.append(created)
    elapsed = round((max(end_times) - min(start_times)) / 1000, 3) if start_times and end_times else None
    total_generated = tokens['reasoning'] + tokens['output']
    summary_files = info.get('summary', {}).get('files')
    signals = []
    if finishes['length']:
        signals.append('generation_limit_reached')
    if repeated_reads:
        signals.append('repeated_read_target_without_recognized_edit')
    if identical_reads:
        signals.append('identical_read_output_without_recognized_edit')
    if uncounted_reasoning:
        signals.append('reasoning_text_without_recorded_token_count')
    if aborted:
        signals.append('aborted_generation')
    if writes == 0 and summary_files == 0:
        signals.append('no_recognized_edit_and_zero_summary_files')
    return {'schema_version': 1, 'messages': len(messages), 'assistant_messages': len(generations),
            'elapsed_seconds': elapsed, 'recorded_tokens': {k: tokens[k] for k in ('input', 'output', 'reasoning')},
            'reasoning_share_of_recorded_generation': round(tokens['reasoning'] / total_generated, 6) if total_generated else None,
            'finishes': dict(finishes), 'tool_calls': dict(tools), 'tool_statuses': dict(statuses),
            'recognized_completed_edit_calls': writes, 'summary_files': summary_files,
            'repeated_read_targets': repeated_reads, 'identical_read_outputs': identical_reads,
            'compactions': compactions, 'aborted_messages': aborted,
            'uncounted_reasoning_chars': uncounted_reasoning, 'generations': generations,
            'signals': signals}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    args = parser.parse_args()
    try:
        with args.session.open(encoding='utf-8') as stream:
            report = analyze(json.load(stream))
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        print('Unable to analyze export: invalid JSON, unreadable file or unsupported structure.', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
