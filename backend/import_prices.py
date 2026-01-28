"""
Script to import UK grocery prices from CSV into the database
Run this once after setting up the database
"""
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import sys

from main import Price, Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/grocery_db")

# Handle Render.com postgres URLs
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def import_csv(csv_path: str):
    """Import prices from CSV file into database"""
    print(f"Reading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    print(f"Found {len(df)} price records")
    
    # Create engine and session
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Clear existing prices
        print("Clearing existing price data...")
        db.query(Price).delete()
        db.commit()
        
        # Import new prices
        print("Importing new prices...")
        for idx, row in df.iterrows():
            # Parse last_updated if present
            last_updated = None
            if 'last_updated' in row and pd.notna(row['last_updated']):
                try:
                    last_updated = pd.to_datetime(row['last_updated']).to_pydatetime()
                except Exception:
                    last_updated = datetime.utcnow()
            else:
                last_updated = datetime.utcnow()
            
            price = Price(
                item=row['item'],
                category=row['category'],
                unit=row['unit'],
                store=row['store'],
                price_per_unit_gbp=float(row['price_per_unit_gbp']),
                last_updated=last_updated,
                notes=row.get('notes', None) if pd.notna(row.get('notes', None)) else None
            )
            db.add(price)
            
            if (idx + 1) % 100 == 0:
                print(f"  Imported {idx + 1} records...")
        
        db.commit()
        print(f"✅ Successfully imported {len(df)} price records!")
        
        # Print some stats
        items = db.query(Price.item).distinct().count()
        stores = db.query(Price.store).distinct().count()
        print(f"📊 Stats: {items} unique items across {stores} stores")
        
    except Exception as e:
        print(f"❌ Error importing data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "uk_grocery_prices.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        print("Usage: python import_prices.py <path_to_csv>")
        sys.exit(1)
    
    import_csv(csv_file)