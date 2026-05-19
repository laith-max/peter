#  Generator

A simple random joke generator that fetches jokes from the [JokeAPI](https://jokeapi.dev/).

## Features

- Fetch random jokes from multiple categories
- Support for different joke types (single, two-part)
- Multiple joke categories: General, Programming, Knock-Knock, Dark, and more
- Error handling for API failures
- Easy-to-use interface

## Installation

```bash
pip install requests
```

## Usage

### Basic Usage

```python
from tools.joke_generator import JokeGenerator

# Create a generator instance
generator = JokeGenerator()

# Get and print a random joke
generator.print_joke()

# Get a specific type of joke
generator.print_joke("Programming")
```

### Supported Joke Types

- `"Any"` - Random joke from any category
- `"General"` - General jokes
- `"Programming"` - Programming/developer jokes
- `"Knock-Knock"` - Knock-knock jokes
- `"Dark"` - Dark humor jokes

### Advanced Usage

```python
# Get joke data as dictionary
joke_data = generator.get_random_joke("Programming")
formatted = generator.format_joke(joke_data)
print(formatted)

# Get joke as JSON
joke_json = generator.get_joke_json("General")
print(joke_json)
```

## Running Tests

```bash
python -m pytest tools/test_joke_generator.py -v
```

## Example Output

```
==================================================
Random Joke Generator
==================================================

🎭 General Joke:
Why did the scarecrow win an award? He was outstanding in his field!

💻 Programming Joke:
Q: Why do programmers prefer dark mode?
A: Because light attracts bugs!

🚪 Knock-Knock Joke:
Q: Knock knock
A: Who's there? Interrupting cow. Interrupting cow wh-- MOOOOO!
```

## API Reference

### JokeGenerator Class

#### Methods

- `get_random_joke(joke_type: str) -> Optional[Dict]`
  - Fetch a random joke of the specified type
  - Returns dictionary with joke data or None on failure

- `format_joke(joke_data: Dict) -> str`
  - Format joke data into readable text
  - Handles both single and two-part jokes

- `print_joke(joke_type: str) -> None`
  - Fetch and print a joke to console

- `get_joke_json(joke_type: str) -> str`
  - Fetch a joke and return as JSON string

## License

MIT
