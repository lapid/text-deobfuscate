"""Clean texts the tool must leave alone: short phrases in other languages, and English with accents.

The tool is English only, so text in another language should come back as it went in. Short
phrases are the risk: a few letters can read as English by chance when reversed or shifted. These
were written for the project (MIT). Dev and test take alternate entries, so no phrase is in both.
"""

from collections.abc import Callable
from random import Random

PHRASES = (
    # Spanish
    "No pasa nada", "Hasta la vista", "Mi casa es su casa", "Buenos dias a todos", "Por favor, ayudame",
    "Como estas hoy", "Que tengas buen dia", "Nos vemos pronto", "Muchas gracias por todo", "Donde esta el bano",
    "Es muy tarde ya", "Voy a la playa", "Dame un poco de agua", "No me gusta nada", "Vamos a comer algo",
    "Tengo mucha hambre", "El gato duerme aqui", "Ella canta muy bien", "Esta noche hay luna", "Todo esta bien",
    # French
    "Ça va très bien", "Merci beaucoup", "Il fait beau aujourd'hui", "Je ne sais pas", "À bientôt mes amis",
    "Bon appétit à tous", "Où est la gare", "C'est la vie", "Je t'aime bien", "Nous allons au marché",
    "Elle parle trop vite", "Un peu de pain", "Il pleut depuis hier", "Quelle belle journée", "Allons voir la mer",
    # German
    "Guten Morgen zusammen", "Ich habe keine Zeit", "Wie geht es dir", "Das ist sehr gut", "Danke schön",
    "Wir fahren nach Hause", "Es regnet schon wieder", "Ich weiß es nicht", "Bis morgen dann", "Der Hund schläft noch",
    # Italian
    "Buona sera a tutti", "Come stai oggi", "Non lo so", "Andiamo al mare", "Grazie mille amico",
    "Mi piace molto", "Che bella giornata", "Dove sei stato", "Ho molta fame", "A presto ragazzi",
    # Portuguese
    "Bom dia para todos", "Muito obrigado", "Eu não sei", "Vamos para casa", "Tudo bem contigo",
    "Que dia lindo hoje", "Onde fica a praia", "Falamos amanhã então", "Estou com sono", "Boa noite meu amigo",
    # Dutch
    "Goedemorgen allemaal", "Ik weet het niet", "Hoe gaat het met je", "Tot ziens morgen", "Het regent weer",
    "Dank je wel", "Wij gaan naar huis", "Dat is heel mooi", "Waar is het station", "Ik heb honger",
)

ACCENTED_ENGLISH = (
    "The naïve café owner updated her résumé on Friday.",
    "We ate crème brûlée at a small café near the old château.",
    "His fiancée sent a pâté sandwich and a cliché of a postcard.",
    "A soupçon of jalapeño went into the piñata-shaped cake.",
    "Her résumé listed a fiancé, a façade restoration and a touché moment.",
    "The protégé wrote a déjà vu story about a café in Zürich.",
    "Naïve readers will not notice the exposé hidden in the appendix.",
    "She ordered a café au lait and a croissant at the brasserie.",
    "The attaché carried a résumé, a cliché and a bouquet of roses.",
    "The señor kept a jalapeño in his coat pocket all afternoon.",
    "Their débâcle at the soirée was a topic over the entrée.",
    "The façade of the old café still has its original sign.",
)


def categories(split: str) -> dict[str, tuple[Callable[[Random], str], int]]:
    """Clean categories for one split; each takes alternate entries of the lists above."""
    half = 0 if split == "dev" else 1
    phrases, accented = PHRASES[half::2], ACCENTED_ENGLISH[half::2]
    return {
        "foreign-phrases": (lambda rng: rng.choice(phrases), len(phrases)),
        "english-with-accents": (lambda rng: rng.choice(accented), len(accented)),
    }
