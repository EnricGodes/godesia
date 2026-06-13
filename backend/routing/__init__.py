"""Capa de routing por intención + slots (castellano).

Reconoce la intención de una pregunta por un vocabulario controlado de lemas
(token completo -> lema) en vez de enumerar tiempos verbales en regex, extrae el
sujeto una sola vez y delega en los handlers ya probados del QueryRouter. Pensado
para crecer intención a intención y, en el futuro, por idioma (añadir un parser,
no reescribir la lógica).
"""

from .intent_es import IntentRouter

__all__ = ["IntentRouter"]
