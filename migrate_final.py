import sqlite3
import os


DB_PATH = os.path.join(
    "instance",
    "eventsphere.db"
)


if not os.path.exists(DB_PATH):

    print("Database not found.")
    exit()


connection = sqlite3.connect(DB_PATH)

cursor = connection.cursor()


# ============================================================
# HELPER
# ============================================================

def table_exists(table_name):

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name=?
        """,
        (table_name,)
    )

    return cursor.fetchone() is not None


def columns(table_name):

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    return [
        row[1]
        for row in cursor.fetchall()
    ]


# ============================================================
# RESOURCES
# ============================================================

if not table_exists("resources"):

    cursor.execute("""
        CREATE TABLE resources (
            resource_id INTEGER PRIMARY KEY,
            resource_name VARCHAR(150) NOT NULL,
            resource_type VARCHAR(100) NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            location VARCHAR(200),
            status VARCHAR(30) NOT NULL DEFAULT 'Available',
            description TEXT
        )
    """)

else:

    existing = columns("resources")

    if "location" not in existing:

        cursor.execute("""
            ALTER TABLE resources
            ADD COLUMN location VARCHAR(200)
        """)

    if "status" not in existing:

        cursor.execute("""
            ALTER TABLE resources
            ADD COLUMN status VARCHAR(30)
            DEFAULT 'Available'
        """)

    if "description" not in existing:

        cursor.execute("""
            ALTER TABLE resources
            ADD COLUMN description TEXT
        """)


# ============================================================
# ATTENDEES
# ============================================================

if not table_exists("attendees"):

    cursor.execute("""
        CREATE TABLE attendees (
            attendee_id INTEGER PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            email VARCHAR(150) NOT NULL,
            phone VARCHAR(30),
            organization VARCHAR(150),
            event_id INTEGER,
            status VARCHAR(30) NOT NULL DEFAULT 'Registered',
            FOREIGN KEY(event_id)
                REFERENCES events(event_id)
        )
    """)


# ============================================================
# EVENT RESOURCES
# ============================================================

if not table_exists("event_resources"):

    cursor.execute("""
        CREATE TABLE event_resources (
            assignment_id INTEGER PRIMARY KEY,
            event_id INTEGER NOT NULL,
            resource_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(event_id)
                REFERENCES events(event_id),
            FOREIGN KEY(resource_id)
                REFERENCES resources(resource_id)
        )
    """)


connection.commit()

connection.close()


print()
print("=" * 60)
print("EVENTSPHERE FINAL DATABASE MIGRATION COMPLETE")
print("=" * 60)
print()