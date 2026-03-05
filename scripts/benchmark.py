"""Benchmark script: measure RAM, CPU and inference speed of the local LLM.

Usage:
    python scripts/benchmark.py [--model models/qwen2.5-3b-instruct-q4_k_m.gguf]

Outputs a markdown table suitable for a technical report.
"""

import argparse
import os
import sys
import time

import psutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def get_memory_mb() -> float:
    proc = psutil.Process(os.getpid())
    return proc.memory_info().rss / 1024 / 1024


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="models/qwen2.5-3b-instruct-q4_k_m.gguf",
        help="Path to GGUF model file",
    )
    parser.add_argument("--n-ctx", type=int, default=2048)
    parser.add_argument("--n-threads", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    print("=" * 60)
    print("  RITM LLM Benchmark")
    print("=" * 60)

    mem_before = get_memory_mb()
    print(f"\nRAM before loading model: {mem_before:.1f} MB")

    t0 = time.time()
    from llama_cpp import Llama

    model = Llama(
        model_path=args.model,
        n_ctx=args.n_ctx,
        n_threads=args.n_threads,
        verbose=False,
    )
    load_time = time.time() - t0
    mem_after = get_memory_mb()
    print(f"RAM after loading model:  {mem_after:.1f} MB")
    print(f"Model memory footprint:   {mem_after - mem_before:.1f} MB")
    print(f"Model load time:          {load_time:.2f} s")

    prompts = [
        "Дай 3 совета по улучшению сна.",
        "Почему белок важен при снижении веса?",
        "Сгенерируй квест на день в JSON: {\"title\": ..., \"category\": ..., \"xp\": ...}",
    ]

    print(f"\nRunning {args.runs} inference rounds (max_tokens={args.max_tokens}) …\n")

    results = []
    for i, prompt in enumerate(prompts):
        times = []
        token_counts = []
        cpu_before = psutil.cpu_percent(interval=None)
        for _ in range(args.runs):
            t1 = time.time()
            out = model.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=args.max_tokens,
                temperature=0.7,
            )
            elapsed = time.time() - t1
            n_tokens = out["usage"]["completion_tokens"]
            times.append(elapsed)
            token_counts.append(n_tokens)
        cpu_after = psutil.cpu_percent(interval=0.5)

        avg_time = sum(times) / len(times)
        avg_tokens = sum(token_counts) / len(token_counts)
        tps = avg_tokens / avg_time if avg_time > 0 else 0

        results.append({
            "prompt": prompt[:50],
            "avg_time": avg_time,
            "avg_tokens": avg_tokens,
            "tokens_per_sec": tps,
            "cpu": cpu_after,
        })
        print(f"  Prompt {i+1}: {avg_time:.2f}s, {avg_tokens:.0f} tokens, {tps:.1f} tok/s")

    mem_peak = get_memory_mb()

    print("\n" + "=" * 60)
    print("  Results (Markdown)")
    print("=" * 60)

    print(f"\n**Model:** `{os.path.basename(args.model)}`  ")
    print(f"**Context:** {args.n_ctx}  ")
    print(f"**Threads:** {args.n_threads}  ")
    print(f"**Load time:** {load_time:.2f}s  ")
    print(f"**RAM (model):** {mem_after - mem_before:.0f} MB  ")
    print(f"**RAM (peak):** {mem_peak:.0f} MB  ")
    print()
    print("| Prompt | Avg time (s) | Tokens | Tok/s | CPU % |")
    print("|--------|-------------|--------|-------|-------|")
    for r in results:
        print(
            f"| {r['prompt']:<50} | {r['avg_time']:.2f} | "
            f"{r['avg_tokens']:.0f} | {r['tokens_per_sec']:.1f} | {r['cpu']:.0f} |"
        )


if __name__ == "__main__":
    main()
