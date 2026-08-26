import sqlite3
import os


# ============================================================
# DATABASE LOCATION
# ============================================================

DB_PATH = os.path.join(
    "instance",
    "eventsphere.db"
)


# ============================================================
# CHECK DATABASE
# ============================================================

if not os.path.exists(DB_PATH):
    print("❌ Database file not found.")
    print(f"Expected location: {DB_PATH}")
    print()
    print("Make sure your Flask application has been run at least once.")
    exit()


print("=" * 60)
print("EventSphere Database Migration")
print("=" * 60)
print()

print(f"Database: {DB_PATH}")
print()


# ============================================================
# CONNECT
# ============================================================

connection = sqlite3.connect(DB_PATH)

cursor = connection.cursor()


# ============================================================
# RESOURCE TABLE
# ============================================================

print("Checking resources table...")


cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    AND name='resources'
""")

resource_table = cursor.fetchone()


if not resource_table:

    print("⚠️ resources table does not exist.")
    print("Creating resources table...")

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

    print("✅ resources table created.")

else:

    print("✅ resources table already exists.")

    # --------------------------------------------------------
    # GET EXISTING COLUMNS
    # --------------------------------------------------------

    cursor.execute("""
        PRAGMA table_info(resources)
    """)

    columns = cursor.fetchall()

    existing_columns = [
        column[1]
        for column in columns
    ]

    print()
    print("Existing columns:")
    print(existing_columns)
    print()

    # --------------------------------------------------------
    # ADD MISSING COLUMNS
    # --------------------------------------------------------

    if "location" not in existing_columns:

        print("Adding missing column: location")

        cursor.execute("""
            ALTER TABLE resources
            ADD COLUMN location VARCHAR(200)
        """)

        print("✅ location column added.")

    else:

        print("✅ location column already exists.")

    # --------------------------------------------------------

    if "status" not in existing_columns:

        print("Adding missing column: status")

        cursor.execute("""
            ALTER TABLE resources
            ADD COLUMN status VARCHAR(30)
            DEFAULT 'Available'
        """)

        print("✅ status column added.")

    else:

        print("✅ status column already exists.")

    # --------------------------------------------------------

    if "description" not in existing_columns:

        print("Adding missing column: description")

        cursor.execute("""
            ALTER TABLE resources
            ADD COLUMN description TEXT
        """)

        print("✅ description column added.")

    else:

        print("✅ description column already exists.")


# ============================================================
# SAVE CHANGES
# ============================================================

connection.commit()


# ============================================================
# VERIFY
# ============================================================

print()
print("Verifying resources table...")
print()

cursor.execute("""
    PRAGMA table_info(resources)
""")

columns = cursor.fetchall()

for column in columns:
    print(
        f"  {column[1]:20} "
        f"{column[2]}"
    )


# ============================================================
# CLOSE
# ============================================================

connection.close()


print()
print("=" * 60)
print("✅ DATABASE MIGRATION COMPLETED SUCCESSFULLY")
print("=" * 60)
print()
print("You can now start EventSphere again.")
print()