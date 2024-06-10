# Simple Trading Platform

Basic trading platform. Built with Django REST

Following must be installed:

- Docker

Steps to run:

1. Run project with command `docker compose up --build -d`
2. Open `http://localhost:8000/api/` on a web browser to access the app api interface
3. For automatic parsing of csv files, it will be fetched on `trade_csvs` directory every minute.

To run via docker:

```
docker compose up --build -d
```

To migrate database:

```
docker compose run --rm backend ./manage.py migrate
```

To create superuser:

```
docker compose run --rm backend ./manage.py createsuperuser
```

To run tests:

```
docker compose run --rm backend pytest
```

To run tests with coverage:

```
docker compose run --rm web coverage run -m pytest
docker compose run --rm web coverage html
```

To stop containers:

```
docker compose down
```