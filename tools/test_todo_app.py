#!/usr/bin/env python3
"""
Unit tests for the To-Do List Application.
"""

import pytest
import json
import tempfile
from pathlib import Path
from tools.todo_app import TodoApp


@pytest.fixture
def temp_storage():
    """Create a temporary storage file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def app(temp_storage):
    """Create a TodoApp instance for testing."""
    return TodoApp(temp_storage)


class TestTodoApp:
    """Test cases for TodoApp."""

    def test_initialization(self, app):
        """Test app initialization."""
        assert app.todos == []
        assert app.storage_file.exists()

    def test_add_todo(self, app):
        """Test adding a todo."""
        app.add_todo("Test task", "Test description", "high")
        assert len(app.todos) == 1
        assert app.todos[0]["title"] == "Test task"
        assert app.todos[0]["description"] == "Test description"
        assert app.todos[0]["priority"] == "high"
        assert app.todos[0]["completed"] is False

    def test_add_empty_todo(self, app, capsys):
        """Test that empty todos are not added."""
        app.add_todo("")
        captured = capsys.readouterr()
        assert "Title cannot be empty" in captured.out
        assert len(app.todos) == 0

    def test_complete_todo(self, app):
        """Test marking a todo as completed."""
        app.add_todo("Task 1")
        app.complete_todo(1)
        assert app.todos[0]["completed"] is True
        assert app.todos[0]["completed_at"] is not None

    def test_complete_nonexistent_todo(self, app, capsys):
        """Test completing a non-existent todo."""
        app.complete_todo(999)
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_delete_todo(self, app):
        """Test deleting a todo."""
        app.add_todo("Task 1")
        app.add_todo("Task 2")
        assert len(app.todos) == 2
        app.delete_todo(1)
        assert len(app.todos) == 1
        assert app.todos[0]["title"] == "Task 2"

    def test_delete_nonexistent_todo(self, app, capsys):
        """Test deleting a non-existent todo."""
        app.delete_todo(999)
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_update_todo(self, app):
        """Test updating a todo."""
        app.add_todo("Original title", "Original description", "low")
        app.update_todo(1, "New title", "New description", "high")
        
        assert app.todos[0]["title"] == "New title"
        assert app.todos[0]["description"] == "New description"
        assert app.todos[0]["priority"] == "high"

    def test_update_partial_fields(self, app):
        """Test updating only some fields."""
        app.add_todo("Original", "Description", "low")
        app.update_todo(1, title="Updated")
        
        assert app.todos[0]["title"] == "Updated"
        assert app.todos[0]["description"] == "Description"
        assert app.todos[0]["priority"] == "low"

    def test_persistence(self, temp_storage):
        """Test that todos are persisted to file."""
        # Create app and add todos
        app1 = TodoApp(temp_storage)
        app1.add_todo("Task 1", "Description 1", "high")
        app1.add_todo("Task 2", "Description 2", "low")
        
        # Create new app instance and verify todos are loaded
        app2 = TodoApp(temp_storage)
        assert len(app2.todos) == 2
        assert app2.todos[0]["title"] == "Task 1"
        assert app2.todos[1]["title"] == "Task 2"

    def test_get_stats(self, app, capsys):
        """Test statistics display."""
        app.add_todo("Task 1", priority="high")
        app.add_todo("Task 2", priority="low")
        app.complete_todo(1)
        
        app.get_stats()
        captured = capsys.readouterr()
        assert "Total tasks: 2" in captured.out
        assert "Completed: 1" in captured.out
        assert "Pending: 1" in captured.out
        assert "High priority: 0" in captured.out

    def test_priority_normalization(self, app):
        """Test that priorities are normalized to lowercase."""
        app.add_todo("Task", priority="HIGH")
        assert app.todos[0]["priority"] == "high"

    def test_list_completed_todos(self, app):
        """Test listing only completed todos."""
        app.add_todo("Task 1")
        app.add_todo("Task 2")
        app.complete_todo(1)
        
        # Filter should return only completed
        completed = [t for t in app.todos if t["completed"]]
        assert len(completed) == 1
        assert completed[0]["title"] == "Task 1"

    def test_list_pending_todos(self, app):
        """Test listing only pending todos."""
        app.add_todo("Task 1")
        app.add_todo("Task 2")
        app.complete_todo(1)
        
        # Filter should return only pending
        pending = [t for t in app.todos if not t["completed"]]
        assert len(pending) == 1
        assert pending[0]["title"] == "Task 2"
