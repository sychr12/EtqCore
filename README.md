# Etiquetas Zebra

Aplicativo local para criar etiquetas ZPL com QR Code e contador persistente.

## Como abrir

Clique duas vezes em `Iniciar Etiquetas Zebra.bat`. O navegador abrirá em
`http://localhost:8080`.

## Segurança do contador

- O próximo número fica em `dados/etiquetas.db` (SQLite com gravação síncrona).
- Cada geração reserva o número em uma transação exclusiva e registra uma linha
  com identificador único.
- Uma falha de impressão **não devolve** o número ao contador.
- Na impressão em lote, cada etiqueta recebe contador e QR próprios; o lote todo
  é reservado antes de ser enviado à impressora.
- As 10 posições depois de `TB` começam numéricas. Depois de `TB9999999999`, a
  sequência continua como `TBA000000000`, `TBA000000001` e assim por diante;
  após `Z`, são usadas duas letras (`AA`, `AB` etc.).
- A pré-visualização não consome número.
- Faça backup frequente pelo botão **Baixar backup do contador** e também da
  pasta `dados`. Não execute duas cópias do aplicativo usando bancos diferentes.

## Impressão

Em **Configurações**, informe o nome exato da impressora instalada no Windows.
O envio é RAW/ZPL. O arquivo de impressão também pode ser baixado com extensão
`.prn` para envio pelo driver ou por outro sistema.

O perfil de impressão é preparado para a **Zebra ZD220**: 203 dpi, largura
imprimível máxima de 104 mm, detecção automática da mídia e velocidade entre
2 e 4 ips. Se a arte sair deslocada, use as correções horizontal e vertical em
Configurações; esses ajustes não alteram as dimensões da etiqueta.

O `.prn` contém comandos ZPL prontos e não é um projeto editável do
ZebraDesigner Essentials. Projetos do ZebraDesigner usam o formato próprio
`.nlbl`; para este aplicativo, edite a etiqueta na tela e use **Imprimir na
Zebra**.

Para guardar os dados e continuar editando depois, use **Salvar etiqueta
editável (.etq)**. Para recuperar, abra o aplicativo e clique em **Abrir etiqueta
salva**. Também é possível carregar os dados de uma impressão anterior pelo
botão **Usar novamente** no histórico. Salvar ou abrir `.etq` não consome o
contador.

Ao iniciar, o formulário recupera automaticamente os dados da etiqueta mais
recente do histórico. Isso não reutiliza o identificador: uma nova geração
sempre recebe o próximo contador disponível.

A filial é editável em **Configurações** e alimenta o campo `(E)` do QR.
Campos do QR: `(E)...(T)...(P)...(D)...(S)...(Q)...(Y)...(I)...(U)...(L)...`.
A quantidade de entrada é multiplicada por 1000 no QR.

O tamanho da fonte é calculado novamente para cada etiqueta, considerando as
dimensões configuradas e a quantidade de texto. A prévia e o ZPL usam a maior
fonte que cabe sem cortes. O QR mantém pelo menos o tamanho-base e só aumenta
quando a etiqueta ou o próprio conteúdo do QR exigem.
