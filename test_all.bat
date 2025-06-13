@echo off
echo Running tests...
echo.

:: 1 - GET /stack/size
curl -X GET "http://localhost:8496/calculator/stack/size"
echo.

:: 2 - PUT /stack/arguments
curl -X PUT "http://localhost:8496/calculator/stack/arguments" -H "Content-Type: application/json" -d "{\"arguments\": [2, 3]}"
echo.

:: 3 - POST /independent/calculate
curl -X POST "http://localhost:8496/calculator/independent/calculate" -H "Content-Type: application/json" -d "{\"arguments\": [4, 2], \"operation\": \"divide\"}"
echo.

:: 4 - GET /stack/size
curl -X GET "http://localhost:8496/calculator/stack/size"
echo.

:: 5 - PUT /logs/level - change stack-logger to DEBUG
curl -X PUT "http://localhost:8496/logs/level?logger-name=stack-logger&logger-level=DEBUG"
echo.

:: 6 - GET /stack/size
curl -X GET "http://localhost:8496/calculator/stack/size"
echo.

:: 7 - GET /stack/operate?operation=fact
curl -X GET "http://localhost:8496/calculator/stack/operate?operation=fact"
echo.

:: 8 - GET /stack/operate?operation=minus
curl -X GET "http://localhost:8496/calculator/stack/operate?operation=minus"
echo.

:: 9 - PUT /stack/arguments
curl -X PUT "http://localhost:8496/calculator/stack/arguments" -H "Content-Type: application/json" -d "{\"arguments\": [8, 5]}"
echo.

:: 10 - GET /stack/operate?operation=minus
curl -X GET "http://localhost:8496/calculator/stack/operate?operation=minus"
echo.

:: 11 - PUT /logs/level - change request-logger to DEBUG
curl -X PUT "http://localhost:8496/logs/level?logger-name=request-logger&logger-level=DEBUG"
echo.

:: 12 - PUT /stack/arguments
curl -X PUT "http://localhost:8496/calculator/stack/arguments" -H "Content-Type: application/json" -d "{\"arguments\": [2, 3]}"
echo.

:: 13 - GET /calculator/history
curl -X GET "http://localhost:8496/calculator/history"
echo.

:: 14 - GET /stack/operate?operation=abs
curl -X GET "http://localhost:8496/calculator/stack/operate?operation=abs"
echo.

:: 15 - DELETE /stack/arguments?count=1
curl -X DELETE "http://localhost:8496/calculator/stack/arguments?count=1"
echo.

:: 16 - GET /stack/size
curl -X GET "http://localhost:8496/calculator/stack/size"
echo.

:: 17 - GET /calculator/history?flavor=STACK
curl -X GET "http://localhost:8496/calculator/history?flavor=STACK"
echo.

echo Tests finished.
pause
