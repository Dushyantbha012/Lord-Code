import sys
import os
from rich.console import Console

# Add src to python path if needed (though running from root should work)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.llm.groq.factory import get_llm_client
from src.cli.chat_loop import ChatLoop

def main():
    console = Console()
    if not Config.validate():
        sys.exit(1)
    
    # Ask for the directory to be used
    current_dir = os.getcwd()
    console.print(f"Current Directory: [bold cyan]{current_dir}[/bold cyan]")
    try:
        target_dir = input(f"Enter target directory (default: {current_dir}): ").strip()
        if target_dir:
            target_dir = os.path.abspath(os.path.expanduser(target_dir))
            if not os.path.exists(target_dir):
                console.print(f"[bold red]Error: Directory '{target_dir}' does not exist.[/bold red]")
                sys.exit(1)
            if not os.path.isdir(target_dir):
                console.print(f"[bold red]Error: '{target_dir}' is not a directory.[/bold red]")
                sys.exit(1)
            os.chdir(target_dir)
            console.print(f"[bold green]Working directory set to:[/bold green] {os.getcwd()}")
        else:
            console.print(f"[bold green]Using default directory:[/bold green] {current_dir}")
    except (EOFError, KeyboardInterrupt):
        console.print("\n[bold red]Operation cancelled.[/bold red]")
        sys.exit(0)

    llm = get_llm_client(Config.DEFAULT_MODEL)
    chat = ChatLoop(llm)
    try:
        chat.run()
    finally:
        if hasattr(chat, 'total_tokens') and chat.total_tokens['total'] > 0:
            console.print(f"\nSession Total: {chat.total_tokens['total']} tokens "
                          f"(P: {chat.total_tokens['prompt']}, C: {chat.total_tokens['completion']})")

if __name__ == "__main__":
    main()
