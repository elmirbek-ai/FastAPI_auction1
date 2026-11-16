import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if len(SECRET_KEY) < 32 or SECRET_KEY in {
    "REPLACE_WITH_A_SEPARATE_RANDOM_JWT_SIGNING_SECRET",
    "CHANGE_ME_TO_A_LONG_RANDOM_UNIQUE_SECRET",
}:
    raise RuntimeError(
        "SECRET_KEY must be a unique random JWT signing secret of at least 32 characters"
    )

ACCESS_TOKEN_EXPIRE_MINUTES = 40
REFRESH_TOKEN_EXPIRE_DAYS = 2
ALGORITHM = "HS256"


class Settings:
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_KEY = os.getenv("GITHUB_KEY")
    GITHUB_LOGIN_CALLBACK = os.getenv("GITHUB_LOGIN_CALLBACK")

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_KEY = os.getenv("GOOGLE_KEY")
    GOOGLE_LOGIN_CALLBACK = os.getenv("GOOGLE_LOGIN_CALLBACK")


settings = Settings()
