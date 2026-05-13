# 📝 To-Do List Application

A simple command-line to-do list manager with local JSON storage.

## Features

✅ **Add Tasks** - Create new to-do items with optional descriptions and priorities
✅ **View Tasks** - Display all tasks or filter by status (completed/pending)
✅ **Complete Tasks** - Mark tasks as completed with timestamps
✅ **Delete Tasks** - Remove tasks from your list
✅ **Update Tasks** - Modify task details
✅ **Persistent Storage** - Tasks saved to `todos.json`
✅ **Statistics** - View completion rates and task metrics
✅ **Priority Levels** - Organize tasks by priority (low, medium, high)
✅ **Interactive Mode** - User-friendly command-line interface

## Installation

No external dependencies required! Uses only Python standard library.

```bash
cd tools
```

## Usage

### Interactive Mode (Recommended)

Start the application in interactive mode:

```bash
python todo_app.py
```

### Command-Line Mode

Run commands directly:

```bash
# Add a task
python todo_app.py add "Buy groceries"

# List all tasks
python todo_app.py list

# Show statistics
python todo_app.py stats
```

## Interactive Commands

| Command | Description | Example |
|---------|-------------|----------|
| `add <title>` | Add a new task | `add Buy groceries` |
| `list` | Show all tasks | `list` |
| `list completed` | Show completed tasks | `list completed` |
| `list pending` | Show pending tasks | `list pending` |
| `complete <id>` | Mark task as completed | `complete 1` |
| `delete <id>` | Delete a task | `delete 1` |
| `update <id>` | Update a task | `update 1` |
| `stats` | Show statistics | `stats` |
| `help` | Display help | `help` |
| `clear` | Clear screen | `clear` |
| `quit` | Exit application | `quit` |

## Example Workflow

```
🎯 Welcome to To-Do List Manager!
Commands: add, list, complete, delete, update, stats, help, quit

> add Buy groceries
Description (optional): Get milk, eggs, bread
Priority (low/medium/high) [medium]: high
✓ Added: Buy groceries

> add Call mom
Description (optional):
Priority (low/medium/high) [medium]: medium
✓ Added: Call mom

> list

================================================================================
📋 To-Do List (2 tasks)
================================================================================

○ [1] 🔴 Buy groceries
   📝 Get milk, eggs, bread
   Created: 2026-05-13

○ [2] 🟡 Call mom
   Created: 2026-05-13

================================================================================

> complete 1
✓ Completed: Buy groceries

> stats

========================================
📊 Statistics
========================================
Total tasks: 2
✓ Completed: 1
○ Pending: 1
🔴 High priority: 0
📈 Completion rate: 50.0%
========================================
```

## Storage Format

Tasks are stored in `todos.json`:

```json
[
  {
    "id": 1,
    "title": "Buy groceries",
    "description": "Get milk, eggs, bread",
    "priority": "high",
    "completed": true,
    "created_at": "2026-05-13T10:30:00.123456",
    "completed_at": "2026-05-13T11:00:00.123456"
  },
  {
    "id": 2,
    "title": "Call mom",
    "description": "",
    "priority": "medium",
    "completed": false,
    "created_at": "2026-05-13T10:35:00.123456",
    "completed_at": null
  }
]
```

## Testing

Run the test suite:

```bash
pytest test_todo_app.py -v
```

### Test Coverage

- ✅ Adding tasks
- ✅ Completing tasks
- ✅ Deleting tasks
- ✅ Updating tasks
- ✅ File persistence
- ✅ Statistics calculation
- ✅ Priority handling
- ✅ Error handling

## API Usage

Use the `TodoApp` class programmatically:

```python
from tools.todo_app import TodoApp

# Initialize
app = TodoApp("my_todos.json")

# Add tasks
app.add_todo("Learn Python", "Complete the tutorials", "high")
app.add_todo("Exercise", priority="medium")

# List tasks
app.list_todos()
app.list_todos("pending")
app.list_todos("completed")

# Manage tasks
app.complete_todo(1)
app.update_todo(2, title="Updated title")
app.delete_todo(1)

# Statistics
app.get_stats()
```

## Priority Icons

- 🔴 **High** - Important, do first
- 🟡 **Medium** - Regular priority
- 🟢 **Low** - Can be done later

## Tips

1. **Use descriptive titles** - Makes your list easier to scan
2. **Add descriptions** - Details help you remember context
3. **Set priorities** - Helps focus on what matters most
4. **Review stats regularly** - Motivates task completion
5. **Backup todos.json** - Keep a copy if data is important

## Requirements

- Python 3.7+
- No external packages required

## License

Open source - feel free to modify and use!
