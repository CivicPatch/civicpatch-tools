# Components

Web components shared by both civicpatch.org and self hosted civicpatch servers.

Demo page at [components.civicpatch.org](https://components.civicpatch.org)

## Development

Congrats! You have found the only project in this repo that doesn't use docker.
If you have issues with this set up I will dockerize it. 😈🐸🔪

- Ensure port 9000 is free.

  ```sh
  lsof -ti:9000 | xargs kill -9
  ```

- Set up .env file (see: ./.env.example)
- Run the following commands

```sh
mise install
npm install
npm run start
```
