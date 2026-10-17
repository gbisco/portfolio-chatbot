$ErrorActionPreference = "Stop"

docker build -f Dockerfile.test -t portfolio-chatbot-test .
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

docker run --rm portfolio-chatbot-test @args
exit $LASTEXITCODE
