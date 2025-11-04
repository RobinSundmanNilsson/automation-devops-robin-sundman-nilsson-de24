# Bygg (-t ger valfri tag till docker containern)
docker build -t py-mini-cli .

# Kör interaktivt (--rm containern tas bort när containtern stängs ner)(-it behövs för input i terminalen)
docker run --rm -it py-mini-cli


docker build -t py-mini-cli .
docker run --rm -it py-mini-cli