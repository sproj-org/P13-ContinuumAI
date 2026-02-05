## How to Run Docker Container

### Pre-requisites

- Copy and paste the example `.env` files into their respective locations:
  - `root/.env.example` → `root/.env`
  - `backend/.env.example` → `backend/.env`
  - `frontend/.env.example` → `frontend/.env`
- Ensure the `backend/.env` file is supplied.

> **Note:** For the frontend to point to our backend URL, the `.env` file to be changed is in the `root` directory. Docker uses the `vite_api_url` from the `.env` file in the root, so it is important to update it correctly. For local development, the provided url works.

### First-Time Setup

If this is your first time running this, just run the following command in the root directory (`/Phase_1`):

```bash
docker compose up
```

This will build the images and then run the container.

### Re-running the Application

- **If your code has not changed**, you can re-run the command above. Docker will check if your images exist and use them to run containers. If the images don’t exist, it will build them first.
- **If your code has changed**, use the following command:

```bash
docker compose up --build
```

This forces a new build of the images, incorporating the new changes. Don’t worry, Docker will use the cache wherever changes were the same. Extra details ahead u can skip: For example:

- If your `requirements.txt` file was the same but the rest of the code changed, Docker will not re-install those dependencies. Instead, it will use the existing cache and only implement the code changes.
- However, if you didn’t change the code but updated `requirements.txt`, the subsequent layers below will be rebuilt. This will take slightly longer than the previous method. Regardless, Docker handles it efficiently.
