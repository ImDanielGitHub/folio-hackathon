import pytest
from folio_api.app import create_app

@pytest.mark.parametrize('url', [
    'sqlite:////tmp/not-production.sqlite3',
    'postgresql+psycopg://localhost/folio',
    'postgresql+psycopg://localhost/folio?sslmode=require',
    'postgresql+psycopg://localhost/folio?sslmode=verify-full',
])
def test_production_requires_verified_database_tls(monkeypatch, url):
    monkeypatch.setenv('FOLIO_ENV', 'production')
    with pytest.raises(ValueError):
        create_app(url)
