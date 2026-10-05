class RuleNotApplicable(Exception):
    """A heurística não encontrou nada para otimizar no código analisado.

    Substitui o comportamento anterior de inserir comentários "fake" que
    geravam patches sem nenhum efeito real.
    """
