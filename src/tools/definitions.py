from typing import List, Dict, Any

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the specified path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the file."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist, or overwrites entirely. For editing existing files, prefer edit_file instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file."
                    },
                    "content": {
                        "type": "string",
                        "description": "The string content to write."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    # ── Diff-Based Editing (Feature 3.1) ──
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit an existing file using search/replace blocks. Much more efficient and safer than write_file for modifying existing files. Shows a unified diff before applying changes. Each edit should contain a 'search' string (exact text to find) and a 'replace' string (text to replace it with).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to edit."
                    },
                    "edits": {
                        "type": "array",
                        "description": "Array of edit operations. Each object should have 'search' (exact text to find) and 'replace' (replacement text) keys.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "search": {
                                    "type": "string",
                                    "description": "The exact text to search for in the file."
                                },
                                "replace": {
                                    "type": "string",
                                    "description": "The text to replace the search text with."
                                }
                            },
                            "required": ["search", "replace"]
                        }
                    }
                },
                "required": ["path", "edits"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command in the system terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact shell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and subdirectories in a given directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for a regex pattern in files. Use for exact pattern matching across files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The regex or string pattern to search for."
                    },
                    "path": {
                        "type": "string",
                        "description": "The path or directory to search in."
                    }
                },
                "required": ["pattern", "path"]
            }
        }
    },
    # ── Smart Search Tools (Feature 2.2) ──
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Find files by name or glob pattern in the project. Respects .gitignore. Use this to locate files when you know part of the filename.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_pattern": {
                        "type": "string",
                        "description": "The file name or glob pattern to search for (e.g., '*.py', 'config*', 'README.md')."
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory to search in. Defaults to current directory.",
                        "default": "."
                    }
                },
                "required": ["name_pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Search for text content across project files. Returns file:line:content matches. Use this to find where specific code, strings, or identifiers appear.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text or pattern to search for in file contents."
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory to search in. Defaults to current directory.",
                        "default": "."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional glob filter for files (e.g., '*.py', '*.js'). Defaults to all files.",
                        "default": "*"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_definition",
            "description": "Find where a function, class, or variable is defined in the codebase. Supports Python, JavaScript/TypeScript, Rust, and Go.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The name of the function, class, or variable to find."
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory to search in. Defaults to current directory.",
                        "default": "."
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    # ── Git Tools (Features 2.2 + 3.4) ──
    {
        "type": "function",
        "function": {
            "name": "get_git_diff",
            "description": "Show current uncommitted changes (both staged and unstaged). Use this to review what has been modified.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_log",
            "description": "Show the last N git commits with hash, author, time, and message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of commits to show (default 10, max 50).",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage all changes and create a git commit with the given message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The commit message."
                    }
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_create_branch",
            "description": "Create and checkout a new git branch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name for the new branch."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff_ref",
            "description": "Show diff against a specific git reference (branch, tag, or commit hash).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "description": "The git reference to diff against (e.g., 'main', 'HEAD~1', 'v1.0.0')."
                    }
                },
                "required": ["ref"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_stash",
            "description": "Stash current uncommitted changes for later retrieval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Optional description for the stash entry."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_unstash",
            "description": "Pop the most recent stash entry to restore previously stashed changes.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show concise git status including branch info and file changes.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    # ── Test Execution (Feature 3.3) ──
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the project's test suite. Auto-detects the testing framework (pytest, npm test, cargo test, go test). Use this after making code changes to verify correctness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Optional specific test file or directory to run. If omitted, runs the full test suite."
                    },
                    "framework": {
                        "type": "string",
                        "description": "Optional framework override: 'pytest', 'npm', 'cargo', or 'go'. Auto-detected if omitted.",
                        "enum": ["pytest", "npm", "cargo", "go"]
                    }
                },
                "required": []
            }
        }
    },
]
