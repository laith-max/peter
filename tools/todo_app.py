#!/usr/bin/env python3
"""
To-Do List Application with Local Storage

A simple command-line to-do list manager that persists tasks to JSON.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import sys


class TodoApp:
    """Simple to-do list application with JSON storage."""

    def __init__(self, storage_file: str = "todos.json"):
        """Initialize the to-do app with storage file.
        
        Args:
            storage_file: Path to JSON file for storing tasks
        """
        self.storage_file = Path(storage_file)
        self.todos: List[Dict] = []
        self.load_todos()

    def load_todos(self) -> None:
        """Load todos from JSON file."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    self.todos = json.load(f)
                print(f"✓ Loaded {len(self.todos)} tasks from {self.storage_file}")
            except json.JSONDecodeError:
                print(f"⚠ Warning: Could not parse {self.storage_file}, starting fresh")
                self.todos = []
        else:
            print(f"📝 Creating new to-do list at {self.storage_file}")
            self.todos = []

    def save_todos(self) -> None:
        """Save todos to JSON file."""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self.todos, f, indent=2)
            print(f"✓ Saved {len(self.todos)} tasks")
        except IOError as e:
            print(f"✗ Error saving todos: {e}")

    def add_todo(self, title: str, description: str = "", priority: str = "medium") -> None:
        """Add a new todo item.
        
        Args:
            title: Task title
            description: Optional task description
            priority: Priority level (low, medium, high)
        """
        if not title.strip():
            print("✗ Title cannot be empty")
            return

        todo = {
            "id": len(self.todos) + 1,
            "title": title,
            "description": description,
            "priority": priority.lower(),
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "completed_at": None
        }
        self.todos.append(todo)
        print(f"✓ Added: {title}")
        self.save_todos()

    def list_todos(self, filter_by: Optional[str] = None) -> None:
        """Display all todos.
        
        Args:
            filter_by: Filter todos ("completed", "pending", or None for all)
        """
        if not self.todos:
            print("📭 No tasks yet. Add one with 'add <title>'")
            return

        filtered = self.todos
        if filter_by == "completed":
            filtered = [t for t in self.todos if t["completed"]]
        elif filter_by == "pending":
            filtered = [t for t in self.todos if not t["completed"]]

        if not filtered:
            print(f"📭 No {filter_by} tasks")
            return

        print("\n" + "=" * 80)
        print(f"📋 To-Do List ({len(filtered)} task{'s' if len(filtered) != 1 else ''})")
        print("=" * 80)

        for todo in filtered:
            status = "✓" if todo["completed"] else "○"
            priority_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(todo["priority"], "○")
            
            print(f"\n{status} [{todo['id']}] {priority_icon} {todo['title']}")
            if todo['description']:
                print(f"   📝 {todo['description']}")
            print(f"   Created: {todo['created_at'][:10]}")
            if todo['completed'] and todo['completed_at']:
                print(f"   Completed: {todo['completed_at'][:10]}")

        print("\n" + "=" * 80)

    def complete_todo(self, todo_id: int) -> None:
        """Mark a todo as completed.
        
        Args:
            todo_id: ID of the todo to complete
        """
        for todo in self.todos:
            if todo["id"] == todo_id:
                if todo["completed"]:
                    print(f"ℹ Task '{todo['title']}' is already completed")
                else:
                    todo["completed"] = True
                    todo["completed_at"] = datetime.now().isoformat()
                    print(f"✓ Completed: {todo['title']}")
                self.save_todos()
                return
        print(f"✗ Task with ID {todo_id} not found")

    def delete_todo(self, todo_id: int) -> None:
        """Delete a todo item.
        
        Args:
            todo_id: ID of the todo to delete
        """
        original_count = len(self.todos)
        self.todos = [t for t in self.todos if t["id"] != todo_id]
        
        if len(self.todos) < original_count:
            print(f"✓ Deleted task with ID {todo_id}")
            self.save_todos()
        else:
            print(f"✗ Task with ID {todo_id} not found")

    def update_todo(self, todo_id: int, title: Optional[str] = None, 
                    description: Optional[str] = None, priority: Optional[str] = None) -> None:
        """Update a todo item.
        
        Args:
            todo_id: ID of the todo to update
            title: New title (optional)
            description: New description (optional)
            priority: New priority (optional)
        """
        for todo in self.todos:
            if todo["id"] == todo_id:
                if title is not None:
                    todo["title"] = title
                if description is not None:
                    todo["description"] = description
                if priority is not None:
                    todo["priority"] = priority.lower()
                print(f"✓ Updated task with ID {todo_id}")
                self.save_todos()
                return
        print(f"✗ Task with ID {todo_id} not found")

    def get_stats(self) -> None:
        """Display statistics about todos."""
        total = len(self.todos)
        completed = sum(1 for t in self.todos if t["completed"])
        pending = total - completed
        high_priority = sum(1 for t in self.todos if t["priority"] == "high" and not t["completed"])

        print("\n" + "=" * 40)
        print("📊 Statistics")
        print("=" * 40)
        print(f"Total tasks: {total}")
        print(f"✓ Completed: {completed}")
        print(f"○ Pending: {pending}")
        print(f"🔴 High priority: {high_priority}")
        if total > 0:
            completion_rate = (completed / total) * 100
            print(f"📈 Completion rate: {completion_rate:.1f}%")
        print("=" * 40)

    def interactive_mode(self) -> None:
        """Run the app in interactive mode."""
        print("\n🎯 Welcome to To-Do List Manager!")
        print("Commands: add, list, complete, delete, update, stats, help, quit\n")

        while True:
            try:
                command = input("\n> ").strip().lower()

                if command == "quit" or command == "q":
                    print("👋 Goodbye!")
                    break

                elif command == "help":
                    self._show_help()

                elif command.startswith("add "):
                    title = command[4:].strip()
                    description = input("Description (optional): ").strip()
                    priority = input("Priority (low/medium/high) [medium]: ").strip() or "medium"
                    self.add_todo(title, description, priority)

                elif command == "list":
                    self.list_todos()

                elif command == "list completed":
                    self.list_todos("completed")

                elif command == "list pending":
                    self.list_todos("pending")

                elif command.startswith("complete "):
                    try:
                        todo_id = int(command.split()[1])
                        self.complete_todo(todo_id)
                    except (ValueError, IndexError):
                        print("✗ Usage: complete <id>")

                elif command.startswith("delete "):
                    try:
                        todo_id = int(command.split()[1])
                        self.delete_todo(todo_id)
                    except (ValueError, IndexError):
                        print("✗ Usage: delete <id>")

                elif command == "stats":
                    self.get_stats()

                elif command == "clear":
                    os.system("clear" if os.name == "posix" else "cls")

                else:
                    print("✗ Unknown command. Type 'help' for available commands.")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"✗ Error: {e}")

    @staticmethod
    def _show_help() -> None:
        """Display help information."""
        help_text = """
        📚 Available Commands:
        
        add <title>          Add a new todo
        list                 Show all todos
        list completed       Show completed todos
        list pending         Show pending todos
        complete <id>        Mark todo as completed
        delete <id>          Delete a todo
        stats                Show statistics
        help                 Show this help message
        clear                Clear screen
        quit                 Exit the application
        """
        print(help_text)


def main():
    """Main entry point."""
    app = TodoApp("todos.json")
    
    if len(sys.argv) > 1:
        # Command-line mode
        command = sys.argv[1].lower()
        
        if command == "add" and len(sys.argv) > 2:
            app.add_todo(" ".join(sys.argv[2:]))
        elif command == "list":
            app.list_todos()
        elif command == "stats":
            app.get_stats()
        else:
            print("Usage: python todo_app.py [add|list|stats] [args]")
    else:
        # Interactive mode
        app.interactive_mode()


if __name__ == "__main__":
    main()
