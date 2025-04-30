from dotenv import dotenv_values

def get_available_env_keys_from_dotenv():
    """Retrieve all available environment variable key names from .env file."""
    dotenv_data = dotenv_values()  
    env_keys = list(dotenv_data.keys())  # Get only the keys
    return env_keys

if __name__ == "__main__":
    keys = get_available_env_keys_from_dotenv()
    print("Available Environment Keys from .env:")
    for key in keys:
        print(key)