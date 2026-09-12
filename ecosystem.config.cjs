module.exports = {
  apps: [
    {
      name: "gpd-api",
      script: "uv",
      args: "run uvicorn gpd.app:app --host 100.67.176.76 --port 4040 --reload",
      cwd: "/home/work/gpd",
      env: {
        GPD_API_HOST: "100.67.176.76",
        GPD_API_PORT: "4040",
        GPD_ACCESS_TOKEN: "dev-local-token",
        PYTHONPATH: "backend/src",
      },
    },
    {
      name: "gpd-web",
      script: "pnpm",
      args: "--filter @gpd/web dev --host 100.67.176.76 --port 4041",
      cwd: "/home/work/gpd",
      env: {
        GPD_API_HOST: "100.67.176.76",
        GPD_API_PORT: "4040",
        GPD_ACCESS_TOKEN: "dev-local-token",
      },
    },
  ],
};
