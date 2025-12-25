import bcrypt

def generate_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

if __name__ == "__main__":
    password = "yourpasswordhere" 
    password_hash = generate_password_hash(password)
    print(f"Хеш пароля: {password_hash}")