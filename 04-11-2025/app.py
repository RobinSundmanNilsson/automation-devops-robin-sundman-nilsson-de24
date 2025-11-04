#!/usr/bin/env python3
import random
import sys

BANNER = """
=================================
    Gissa talet - super enkel
=================================
Gissa ett tal mellan 1 och 100.
Tryck Ctrl+C för att avsluta.
"""

def ask_int(prompt: str) -> int:
    while True:
        try:
            val = input(prompt).strip()
            if val.lower() in {"q", "quit", "exit"}:
                print("Hejdå!")
                sys.exit(0)
            return int(val)
        except ValueError:
            print("Skriv ett heltal tack (eller 'q' för att avsluta).")
        except EOFError:
            print("\nEOF - avslutar.")
            sys.exit(0)

def play_round():
    secret = random.randint(1, 100)
    tries = 0
    print(BANNER)
    while True:
        guess = ask_int("Din gissning: ")
        tries += 1
        if guess < secret:
            print("För lågt.")
        elif guess > secret:
            print("För högt.")
        else:
            print(f"Rätt! Du behövde {tries} försök.")
            break

def main():
    random.seed()
    try:
        while True:
            play_round()
            again = input("Igen? (j/n): ").strip().lower()
            if not again.startswith("j"):
                print("Klart! 👋")
                break
    except KeyboardInterrupt:
        print("\nAvbrutet. Hejdå!")

if __name__ == "__main__":
    main()