"""
Script to create a super admin user for the ContinuumAI platform.
Run this once during initial setup.

Usage:
    python -m scripts.create_admin --username admin --email admin@continuumai.com --password <secure_password>
"""

import argparse
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal, engine
from app.db.models import Base, User, Organization
from app.core.security import get_password_hash


def create_admin_user(username: str, email: str, password: str, org_name: str = None):
    """Create a super admin user."""
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            print(f"Error: User with username '{username}' or email '{email}' already exists.")
            return False
        
        # Create default admin organization if specified
        organization = None
        if org_name:
            # Check if org exists
            organization = db.query(Organization).filter(Organization.slug == "admin").first()
            if not organization:
                organization = Organization(
                    name=org_name,
                    slug="admin",
                    description="Administrative organization"
                )
                db.add(organization)
                db.commit()
                db.refresh(organization)
                print(f"Created organization: {org_name}")
        
        # Create admin user
        hashed_password = get_password_hash(password)
        admin_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_admin=True,
            is_active=True,
            organization_id=organization.id if organization else None
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"\n✅ Admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Organization: {organization.name if organization else 'None'}")
        print(f"\n   You can now log in at /admin/login")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {e}")
        return False
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create a super admin user for ContinuumAI")
    parser.add_argument("--username", "-u", required=True, help="Admin username")
    parser.add_argument("--email", "-e", required=True, help="Admin email")
    parser.add_argument("--password", "-p", required=True, help="Admin password (min 6 characters)")
    parser.add_argument("--org-name", "-o", default="ContinuumAI Admin", help="Organization name for admin (optional)")
    
    args = parser.parse_args()
    
    if len(args.password) < 6:
        print("Error: Password must be at least 6 characters long")
        sys.exit(1)
    
    success = create_admin_user(
        username=args.username,
        email=args.email,
        password=args.password,
        org_name=args.org_name
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
