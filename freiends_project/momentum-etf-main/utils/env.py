def load_env_if_present() -> bool:
    """Load variables from a .env file if python-dotenv is available.

    Returns True if a .env file was found and loaded.
    """
    try:
        from dotenv import find_dotenv, load_dotenv  # type: ignore
    except Exception:
        return False

    env_path = find_dotenv()
    if not env_path:
        return False
    # override=True를 사용해 장시간 실행되는 프로세스에서도 값을 새로 고친다
    return bool(load_dotenv(env_path, override=True))
