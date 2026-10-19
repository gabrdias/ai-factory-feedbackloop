"""Léxicos usados pela sanitização de nomes de pessoas (ver feedbackloop/pii.py).

Listas genéricas de nomes e sobrenomes comuns no Brasil. Não foram ajustadas aos
dados de avaliação: os nomes "fora do léxico" de tests/data/pii_avaliacao.jsonl
estão ausentes de propósito, para medir a capacidade de generalizar.

Ficaram de fora nomes que também são palavras comuns ou lugares (ex.: Rosa, Paz,
Luz, Sol, Vera, Cruz, Vitória), para reduzir falsos positivos.
"""

PRIMEIROS_NOMES = (
    # masculinos
    "Adriano", "Alan", "Alberto", "Alexandre", "Alex", "Alisson", "Allan", "Álvaro",
    "Anderson", "André", "Ângelo", "Antônio", "Antonio", "Arthur", "Artur", "Augusto",
    "Benedito", "Bernardo", "Breno", "Bruno", "Caio", "Camilo", "Carlos", "Cássio",
    "Celso", "César", "Cláudio", "Claudio", "Cristiano", "Daniel", "Danilo", "Davi",
    "Diego", "Diogo", "Douglas", "Edgar", "Edson", "Eduardo", "Elias", "Elton",
    "Emerson", "Enzo", "Erick", "Everton", "Fabiano", "Fábio", "Fabio", "Felipe",
    "Fernando", "Filipe", "Flávio", "Flavio", "Francisco", "Frederico", "Gabriel",
    "Gilberto", "Gilson", "Giovani", "Guilherme", "Gustavo", "Heitor", "Helder",
    "Henrique", "Hugo", "Humberto", "Igor", "Ivan", "Jair", "Jefferson", "Jeferson",
    "Joaquim", "João", "Joao", "Jonas", "Jorge", "José", "Jose", "Júlio", "Julio",
    "Kleber", "Leandro", "Leonardo", "Leonel", "Lucas", "Luciano", "Luís", "Luis",
    "Luiz", "Marcelo", "Márcio", "Marcio", "Marco", "Marcos", "Mário", "Mario",
    "Mateus", "Matheus", "Maurício", "Mauricio", "Miguel", "Murilo", "Nelson",
    "Nicolas", "Otávio", "Octávio", "Paulo", "Pedro", "Rafael", "Raimundo", "Ramon",
    "Raul", "Renan", "Renato", "Ricardo", "Roberto", "Rodrigo", "Rogério", "Rogerio",
    "Ronaldo", "Rubens", "Samuel", "Sandro", "Sérgio", "Sergio", "Silvio", "Sílvio",
    "Tadeu", "Thiago", "Tiago", "Tomás", "Valter", "Vinícius", "Vinicius", "Vítor",
    "Vitor", "Wagner", "Wallace", "Wellington", "Wesley", "William", "Wilson",
    "Yago", "Yuri",
    # femininos
    "Adriana", "Alessandra", "Alice", "Aline", "Amanda", "Amélia", "Ana", "Andréa",
    "Andrea", "Angélica", "Aparecida", "Bárbara", "Beatriz", "Bianca", "Bruna",
    "Camila", "Carla", "Carmen", "Carolina", "Catarina", "Cecília", "Célia", "Clara",
    "Cláudia", "Cristiane", "Cristina", "Daniela", "Débora", "Denise", "Eduarda",
    "Elaine", "Eliane", "Elisa", "Fabiana", "Fátima", "Fernanda", "Flávia",
    "Gabriela", "Gisele", "Giovana", "Glória", "Helena", "Heloísa", "Ingrid",
    "Irene", "Isabel", "Isabela", "Jaqueline", "Jéssica", "Joana", "Júlia", "Julia",
    "Juliana", "Kátia", "Larissa", "Laura", "Leila", "Letícia", "Lívia", "Luana",
    "Lúcia", "Lucia", "Luciana", "Luísa", "Luiza", "Marcela", "Márcia", "Maria",
    "Mariana", "Marina", "Marta", "Michele", "Michelle", "Mônica", "Nádia",
    "Natália", "Nathalia", "Olívia", "Paloma", "Patrícia", "Paula", "Priscila",
    "Rafaela", "Raquel", "Regina", "Renata", "Rita", "Roberta", "Rosana", "Sabrina",
    "Sandra", "Sheila", "Silvia", "Sílvia", "Simone", "Solange", "Sônia", "Suzana",
    "Tânia", "Tatiana", "Teresa", "Tereza", "Thaís", "Valéria", "Vanessa",
    "Verônica", "Viviane", "Yasmin", "Zilda",
    # apelidos comuns
    "Zé", "Chico", "Beto", "Dudu", "Gui", "Léo", "Leo", "Rafa", "Gabi", "Fê", "Bia",
    "Ju", "Edu", "Mari", "Pri", "Carol", "Tati", "Nando", "Duda", "Dani", "Fabi",
    "Cris", "Zeca", "Juca",
)

SOBRENOMES = (
    "Silva", "Santos", "Oliveira", "Souza", "Sousa", "Rodrigues", "Ferreira", "Alves",
    "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida",
    "Lopes", "Soares", "Fernandes", "Vieira", "Barbosa", "Rocha", "Dias", "Nascimento",
    "Andrade", "Moreira", "Nunes", "Marques", "Machado", "Mendes", "Freitas",
    "Cardoso", "Ramos", "Gonçalves", "Santana", "Teixeira", "Antunes", "Monteiro",
    "Araújo", "Cavalcanti", "Moura", "Campos", "Pinto", "Correia", "Melo", "Medeiros",
    "Azevedo", "Cunha", "Pires", "Siqueira", "Prado", "Pacheco", "Borges", "Batista",
    "Miranda", "Duarte", "Barros", "Guimarães", "Castro", "Lacerda", "Peixoto",
    "Tavares", "Xavier", "Franco", "Farias", "Brito", "Reis", "Rezende", "Coelho",
    "Assis", "Bezerra", "Fonseca", "Paiva", "Vasconcelos", "Sampaio", "Bastos",
    "Nogueira", "Leite", "Magalhães", "Leal", "Dantas", "Viana", "Matos", "Amaral",
    "Moraes", "Morais", "Ferraz", "Lemos", "Rangel", "Sales", "Toledo", "Diniz",
    "Macedo", "Cordeiro", "Braga", "Mota", "Motta", "Neves",
)
