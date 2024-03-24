import sys
import uvicorn
from its.app import create_web_app


def main() -> None:
    args: list = sys.argv[1:]
    port: int = int(args[args.index("-p") + 1])

    web_app = create_web_app()

    uvicorn.run(
        app=web_app,
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
