from app import app, db  # Import Flask app and SQLAlchemy instance
from sqlalchemy import inspect, text  # Import inspector and text for raw queries
from tabulate import tabulate  # Import tabulate for table formatting

with app.app_context():  # Ensure Flask app context
    inspector = inspect(db.engine)  # Create inspector object
    tables = inspector.get_table_names()  # Get all table names

    for table in tables:
        print(f"\nTable: {table}\n")

        # Execute PRAGMA statement correctly using db.session.execute()
        result = db.session.execute(text(f"PRAGMA table_info({table})"))

        # Fetch column details
        columns = [
            ["Column Name", "Type", "Not Null", "Default", "Primary Key"]
        ]
        for row in result.fetchall():
            column_id, name, data_type, not_null, default_value, primary_key = row
            columns.append([name, data_type, bool(not_null), default_value, bool(primary_key)])

        # Print table using tabulate
        print(tabulate(columns, headers="firstrow", tablefmt="grid"))
