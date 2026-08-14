"""CLI entry point for Mecha."""

import argparse
import sys
import os
from mecha import __version__
from mecha.config import Config
from mecha.credentials import set_key, clear_key, has_key, get_key
from mecha.llm.deepseek import DeepSeekLLM
from mecha.loop import run_loop, run_conversation


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mecha",
        description="Mecha — A safety-first Coding Agent Harness",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task description for the agent to execute",
    )
    parser.add_argument(
        "--version", action="version", version=f"mecha {__version__}"
    )
    parser.add_argument(
        "--config",
        default=".mecha.yaml",
        help="Path to config file (default: .mecha.yaml)",
    )
    parser.add_argument(
        "--project-root",
        default=os.getcwd(),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show credential and configuration status",
    )
    parser.add_argument(
        "--set-key", action="store_true",
        help="Set or update the DeepSeek API key",
    )
    parser.add_argument(
        "--clear-key", action="store_true",
        help="Remove the stored API key",
    )

    args = parser.parse_args()

    if args.status:
        _cmd_status(args)
        return
    if args.set_key:
        _cmd_set_key()
        return
    if args.clear_key:
        _cmd_clear_key()
        return

    if args.task:
        _cmd_run(args)
    else:
        _cmd_repl(args)


def _cmd_status(args) -> None:
    print("Mecha Status")
    print("============")
    print(f"  Version: {__version__}")
    if has_key():
        print("  API Key:  [configured]")
    else:
        print("  API Key:  [not configured] — run 'mecha --set-key' to configure")
    config = Config.from_file(args.config)
    print(f"  LLM Provider: {config.llm_provider}")
    print(f"  LLM Model:    {config.llm_model}")
    print(f"  Max Iterations: {config.max_iterations}")
    print(f"  Config file:  {args.config}")


def _cmd_set_key() -> None:
    backend = set_key()
    if backend == "keyring":
        print("API key saved to OS keyring.")
    else:
        print("API key saved to encrypted fallback file (~/.mecha/credentials.enc).")


def _cmd_clear_key() -> None:
    clear_key()
    print("API key removed.")


def _cmd_run(args) -> None:
    config = Config.from_file(args.config)
    api_key = get_key()
    if api_key is None:
        print("No API key configured. Run 'mecha --set-key' first.")
        sys.exit(1)
    llm = DeepSeekLLM(config, api_key)
    print(f"\nMecha is working on: {args.task}\n")
    result = run_loop(args.task, llm, config, args.project_root)
    print(f"\n{'='*50}")
    if result["success"]:
        print(f"Task completed in {result['iterations']} iterations.")
        print(f"Summary: {result['summary']}")
    else:
        print(f"Task failed after {result['iterations']} iterations.")
        print(f"Reason: {result['summary']}")
    _print_usage(llm)
    print(f"{'='*50}\n")


def _cmd_repl(args) -> None:
    config = Config.from_file(args.config)
    api_key = get_key()
    if api_key is None:
        print("No API key configured. Run 'mecha --set-key' first.")
        sys.exit(1)
    llm = DeepSeekLLM(config, api_key)
    run_conversation(llm, config, args.project_root)


def _print_usage(llm: DeepSeekLLM) -> None:
    """Print token usage summary."""
    u = llm.last_usage
    t = llm.total_tokens
    print(f"Tokens: {u['total_tokens']} this call | {t} total (P:{llm.total_prompt_tokens} C:{llm.total_completion_tokens})")


if __name__ == "__main__":
    main()
