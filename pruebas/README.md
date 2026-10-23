# Pruebas

```bash
pip install -r requirements-ci.txt
pytest pruebas -v
```

86 pruebas, pocos segundos, y **sin los datos de DSMarket**.

Esa última parte no es una casualidad: es la decisión de diseño de la que depende todo lo demás.
Una suite que exige 469 MB de ficheros propiedad de la escuela es una suite que no se ejecuta en
un servidor de integración continua, y por tanto una suite que no se ejecuta nunca.

## Qué se prueba, y por qué eso

| Fichero | Pruebas | Qué cubre |
|---|---|---|
| `test_politica.py` | 28 | La aritmética que decide cuánto stock se pide |
| `test_contratos.py` | 28 | Que cada contrato detecta la violación que dice detectar |
| `test_promocion.py` | 13 | Que un candidato peor no llega a producción |
| `test_registro.py` | 9 | El ciclo de vida del modelo, sobre un registro temporal |
| `test_metricas.py` | 8 | Que el PSI mide deriva y no ruido |

El servicio web dispone de trece comprobaciones de humo y ninguna sobre la política de reposición.
Es el reparto habitual y está al revés: un fallo del servicio se ve en el acto, un error en la
fórmula del stock de seguridad se ve cuando falta mercadería.

## Las dos pruebas que más importan

**La identidad del vendedor de periódicos.** `test_el_coste_del_vendedor_de_periodicos_es_pinball_reescalada`
verifica por muestreo que **C(S) = (Cu + Co) · L_τ*(D − S)**. Sobre esa igualdad se apoya medio
capítulo §7.4: si alguien rompe una fórmula, el argumento de elegir el modelo por coste de
negocio deja de ser cierto, y esta prueba lo dice en dos segundos en vez de en la defensa.

**El cruce de cuantiles.** `test_detecta_el_cruce_de_cuantiles` es una prueba de regresión de un
defecto real: 25.296 filas con el percentil 90 por debajo de la media, que dejaban sin stock de
seguridad al 22% de la celda CZ —justo el segmento de demanda más errática—. Lo encontró un
contrato sobre el almacén de verdad; esta prueba existe para que no pueda volver en silencio.

## El almacén de juguete

`conftest.py` construye en memoria un almacén con las mismas tablas que el de verdad y cuatro
filas cada una: dos productos, dos tiendas, tres días. Pasa todos los contratos limpio. Cada
prueba lo rompe **de una manera distinta** y comprueba que salta el contrato correspondiente.

Un contrato que nunca ha fallado no está probado: está sin estrenar.

Dos contratos no se pueden probar así y se declaran aparte en `NO_APLICABLES`: el que exige que
`dim_serie` tenga exactamente 30.490 filas —un almacén de juguete nunca las tendrá— y el de
frescura, que compara con la fecha de hoy. Los cubre la ejecución real.

## El orden

`pytest-randomly` baraja el orden en cada ejecución, y la integración continua ejecuta la suite
dos veces. Una prueba que solo pasa en su orden habitual depende de un estado que no declaró, y
sale más barato descubrirlo aquí.
