"""Rendu des réponses d'agents : lisible, et jamais de HTML venu du modèle."""

from boussole.ui.markdown import render


def test_model_output_cannot_inject_html() -> None:
    html = render('<script>alert(1)</script> **gras** <img src=x onerror="y">')
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and "<strong>gras</strong>" in html


def test_headings_lists_and_paragraphs() -> None:
    html = render("### Livrables\n\n- Lot 1 [1]\n- Lot 2\n\n1. Valider\n2. Lancer\n\nTexte\nsuite")
    assert "<h4>Livrables</h4>" in html
    assert "<ul><li>Lot 1 [1]</li><li>Lot 2</li></ul>" in html
    assert "<ol><li>Valider</li><li>Lancer</li></ol>" in html
    assert "<p>Texte<br>suite</p>" in html


def test_tables_skip_the_rule_row() -> None:
    html = render("| Risque | Score |\n|---|---:|\n| Migration | **16** |")
    assert "<th>Risque</th><th>Score</th>" in html
    assert "<td>Migration</td><td><strong>16</strong></td>" in html
    assert "---" not in html


def test_code_blocks_are_kept_verbatim_and_escaped() -> None:
    html = render("Avant\n```markdown\n# Titre\n- <b>item</b>\n```\nAprès")
    assert '<pre class="code"># Titre\n- &lt;b&gt;item&lt;/b&gt;</pre>' in html
    assert "<h4>" not in html and "<p>Avant</p>" in html and "<p>Après</p>" in html
