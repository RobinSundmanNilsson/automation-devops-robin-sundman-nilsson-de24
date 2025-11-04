# Bygg (-t ger valfri tag till docker containern)
docker build -t py-mini-game .

# Kör interaktivt (--rm containern tas bort när containtern stängs ner)(-it behövs för input i terminalen)
docker run --rm -it py-mini-game


docker build -t py-mini-game .
docker run --rm -it py-mini-game