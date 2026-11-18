"""Start the pilot over: delete the database and seed it again from data/."""

from backend import db

if __name__ == "__main__":
    db.reset()
    print(f"Seeded {db.path()}")
