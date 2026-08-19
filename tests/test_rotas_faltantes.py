import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-role")
os.environ.setdefault("JWT_SECRET", "test-secret")

from backend.app.main import RetornoPayload, _id_inteiro, _normalizar_hora_retorno, app

assert _normalizar_hora_retorno(None).count(":") == 2
assert _normalizar_hora_retorno("07:05") == "07:05:00"
assert _normalizar_hora_retorno("07:05:09") == "07:05:09"
assert RetornoPayload().hora_fim is None
assert _id_inteiro("12") == 12

try:
    _id_inteiro("0")
except Exception as exc:
    assert getattr(exc, "status_code", None) == 422
else:
    raise AssertionError("ID zero deveria ser rejeitado")

routes = {(route.path, tuple(sorted(route.methods or []))) for route in app.routes}
assert ("/api/apontamentos/{id}/retornar", ("POST",)) in routes
assert ("/api/oee", ("GET",)) in routes
print("OK: helpers e rotas validados sem acesso ao Supabase")
