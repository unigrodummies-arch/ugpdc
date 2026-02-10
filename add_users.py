from app import app, db, User

def add_new_user(username, password):
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"User '{username}' already exists.")
            return

        # Add the new user
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        print(f"Successfully added user: {username}")

if __name__ == '__main__':
    # Add your 5 users here
    add_new_user('uma', '0110')
    