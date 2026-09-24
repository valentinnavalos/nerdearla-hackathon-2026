from backend.core.glossary import Glossary


def test_replacement_is_case_insensitive():
    g = Glossary(replacements={"cubernetes": "Kubernetes"})
    assert g.apply("Deploy en Cubernetes y CUBERNETES") == "Deploy en Kubernetes y Kubernetes"


def test_replacement_respects_word_boundaries():
    g = Glossary(replacements={"go": "Go"})
    assert g.apply("google go gopher") == "google Go gopher"


def test_terms_normalize_capitalization():
    g = Glossary(terms=["Kubernetes", "Nerdearla"])
    assert g.apply("bienvenidos a nerdearla, hoy kubernetes") == "bienvenidos a Nerdearla, hoy Kubernetes"


def test_terms_with_special_characters():
    g = Glossary(terms=["C++", "Node.js", ".NET"])
    assert g.apply("uso c++, node.js y .net") == "uso C++, Node.js y .NET"


def test_replacements_run_before_terms_and_longest_first():
    g = Glossary(terms=["Nerdearla"], replacements={"nerd earla": "Nerdearla", "earla": "ERROR"})
    assert g.apply("esto es nerd earla") == "esto es Nerdearla"


def test_parse_text():
    g = Glossary.parse_text("Kubernetes\n\n# comentario\ncubernetes => Kubernetes\n  Terraform  \n")
    assert g.terms == ["Kubernetes", "Terraform"]
    assert g.replacements == {"cubernetes": "Kubernetes"}


def test_merge_session_wins():
    base = Glossary(terms=["kubernetes", "Gemini"], replacements={"cubernetes": "Kubernetes", "jemini": "Gemini"})
    session = Glossary(terms=["Kubernetes", "Terraform"], replacements={"Cubernetes": "K8s"})
    merged = Glossary.merge(base, session)
    assert merged.terms == ["Kubernetes", "Terraform", "Gemini"]
    assert merged.replacements == {"cubernetes": "K8s", "jemini": "Gemini"}
    assert Glossary.merge(None, None).apply("hola") == "hola"
