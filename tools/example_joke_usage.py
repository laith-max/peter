#!/usr/bin/env python3
"""
Example usage of the JokeGenerator module.

This script demonstrates how to use the JokeGenerator class
to fetch and display random jokes from the JokeAPI.
"""

from tools.joke_generator import JokeGenerator

# Create a generator instance
generator = JokeGenerator()

print("=" * 60)
print("🎭 RANDOM JOKE GENERATOR EXAMPLES")
print("=" * 60)

# Example 1: Get and print a random joke
print("\n1️⃣  Random Joke (Any Category):")
print("-" * 60)
generator.print_joke()

# Example 2: Get a specific type of joke (Programming)
print("\n2️⃣  Programming Joke:")
print("-" * 60)
generator.print_joke("Programming")

# Example 3: Get a General joke
print("\n3️⃣  General Joke:")
print("-" * 60)
generator.print_joke("General")

# Example 4: Get a Knock-Knock joke
print("\n4️⃣  Knock-Knock Joke:")
print("-" * 60)
generator.print_joke("Knock-Knock")

# Example 5: Get a Dark joke
print("\n5️⃣  Dark Humor Joke:")
print("-" * 60)
generator.print_joke("Dark")

# Example 6: Get joke as JSON
print("\n6️⃣  Joke as JSON:")
print("-" * 60)
joke_json = generator.get_joke_json("Programming")
print(joke_json)

print("\n" + "=" * 60)
print("✨ Examples completed!")
print("=" * 60)
