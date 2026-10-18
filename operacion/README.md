# Capa de operación

Lo que convierte cuatro cuadernos en un sistema. Colocá esta carpeta como `PROYECTO/operacion/`
y ejecutá desde `PROYECTO/`.

```bash
python3 operacion/orquestador.py              # todo, de principio a fin
python3 operacion/orquestador.py --simular    # el plan, sin ejecutar nada
python3 operacion/orquestador.py --estado     # qué pasó en las últimas ejecuciones
```

## Por qué existe

Antes de esto el proyecto se ejecutaba abriendo cuadernos en un orden que había que recordar.
Eso no es un sistema: es un procedimiento que vive en la cabeza de quien lo montó. Un sistema se
reconoce en cuatro cosas, y las cuatro están aquí:

| Se reconoce en que… | Fichero |
|---|---|
| se lanza entero con un comando y sabe en qué etapa está | `orquestador.py` |
| se detiene cuando los datos están mal, en vez de publicar basura | `contratos.py` |
| sabe qué modelo produjo qué predicción, y de qué está hecho | `modelos.py`, `procedencia.py` |
| **no deja que un modelo peor sustituya en silencio al que funcionaba** | `promocion.py` |
| se puede deshacer más rápido de lo que se diagnostica | `modelos.py --retroceder` |
| se entera de que se está degradando sin que nadie mire | `monitor.py` |
| hace algo con esa señal en vez de escribirla y ya | `lazo.py` |
| tiene una política probada y no solo ejecutada | `politica.py` + `pruebas/` |

## Las diez etapas

```
bronce → plata → oro → contratos → entrenar → promocion → predecir → reposicion → contratos → monitor
```

Los contratos corren **dos veces a propósito**: después de construir el almacén y otra vez antes
de publicar. La segunda pasada es la que impide que un modelo roto llegue a la API.

Las etapas bloqueantes detienen el pipeline. `monitor` no bloquea: una alerta es información, no
un motivo para no publicar.

`promocion` es la etapa con el comportamiento menos evidente, y a propósito: **rechazar al
candidato no es fallar**. Cuando el modelo nuevo no mejora, la etapa devuelve éxito y el pipeline
sigue prediciendo con el vigente de siempre. Solo detiene el proceso cuando no hay ningún modelo
con el que continuar, es decir, en el primer entrenamiento.

## Los ficheros

**`orquestador.py`** — Ejecuta las etapas en orden, cronometra cada una y escribe el resultado en
`fact_ejecuciones`. `--desde <etapa>` reanuda donde se quedó; `--solo <etapa>` ejecuta una sola.

**`contratos.py`** — Quince contratos de datos. La diferencia entre un contrato y una comprobación
de calidad es qué pasa cuando falla: una comprobación avisa, un contrato **detiene**. Un almacén
que publica datos rotos porque la comprobación solo escribió una advertencia que nadie lee es
peor que uno que no comprueba nada, porque da una falsa sensación de control.

**`modelos.py`** — Registro de modelos **con estados**. Cada entrenamiento da de alta una fila en
`dim_modelo` con hiperparámetros, ventana, fecha de corte, métricas y procedencia, y su
identificador viaja con cada predicción. Responde la pregunta que alguien acaba haciendo: «este
pedido de hace tres semanas, ¿con qué modelo se calculó?».

```
candidato ──(puerta)──> vigente ──(entra otro)──> retirado
    │                       ^                         │
    └──(la puerta rechaza)  └──── retroceso ──────────┘
            v
        rechazado
```

Solo hay un `vigente` por tipo y es el único que predice. El rechazado **no se borra**: el
histórico de lo que no se promovió es la mitad de la información útil cuando algo va mal.

```bash
python3 operacion/modelos.py                # el registro completo
python3 operacion/modelos.py --vigente      # solo el que manda, con su procedencia
python3 operacion/modelos.py --retroceder   # volver al anterior, sin reentrenar
```

**`procedencia.py`** — De qué está hecho cada modelo: el SHA del commit —con sufijo `+sucio` si
el árbol tenía cambios sin comitear, porque entonces no es reconstruible—, una huella del almacén
que el entrenamiento leyó, y las versiones de las cinco bibliotecas que deciden el resultado
numérico. Las tres hacen falta: con la fecha sola no alcanza, porque dos entrenamientos del mismo
día ven almacenes distintos si alguien reconstruyó la capa de plata en medio.

**`promocion.py`** — La puerta. Cuatro reglas: cobertura del p90 dentro de la banda 85–95%, MAE
que no empeore más de un 5% frente al vigente (el margen no es cero porque el ruido entre dos
ventanas de validación es de ese orden), árbol de trabajo limpio y contratos en verde.

**`entrenar.py`** — Los ocho modelos (cuatro bloques × media y p90), guardados en disco. Guardar
el modelo es lo que separa esto de un cuaderno: la predicción de mañana no reentrena, carga. Lo
que sale de aquí es un **candidato**: entrenar ya no despliega.

**`politica.py`** — La política de reposición sin datos alrededor: razón crítica, niveles por
celda ABC/XYZ, stock de seguridad, coste del vendedor de periódicos. Estaba dentro de
`reposicion.py` y por eso no se podía probar. Separarla no cambió ningún número; cambió que ahora
hay veinte pruebas que saltan si alguien toca la fórmula.

**`lazo.py`** — Cierra el lazo entre el monitor y el entrenamiento. Reentrena si hay dos
ejecuciones seguidas en alerta o si el modelo vigente pasa de 28 días; **no** reentrena si los
contratos no están en verde —reentrenar sobre datos rotos produce un modelo roto con métricas
nuevas— ni si ya se reentrenó hace menos de siete días. Y reentrenar no es promover: lo que sale
es un candidato. El lazo automatiza el trabajo, no la decisión.

**`fijar_entorno.py`** — Genera y comprueba `requirements-bloqueado.txt`. `requirements.txt`
instala el proyecto; este lo reproduce.

**`predecir.py`** — Carga los modelos vigentes y predice los 28 días siguientes. El precio futuro
se arrastra del último observado; es un supuesto declarado, no un descuido: si la compañía
planifica un cambio de precio, ese precio debería entrar aquí.

**`reposicion.py`** — Niveles objetivo por serie con la política híbrida. No decide el pedido
—para eso hace falta el stock, que el sistema no tiene—, deja calculada la parte que sí depende
de los datos.

**`monitor.py`** — Vigila tres cosas distintas, y conviene no confundirlas:

1. **Error realizado.** Cuando vencen las predicciones, se comparan con lo ocurrido. Es la medida
   verdadera y llega tarde por definición.
2. **Deriva de las entradas** (PSI sobre unidades y precio). Se detecta el mismo día, sin esperar
   al resultado.
3. **Deriva de la predicción.** Si el modelo empieza a predecir distinto de su propio histórico,
   algo cambió aunque las entradas parezcan normales.

## Dónde queda todo

```
lakehouse/gold/operacion/
    fact_ejecuciones.parquet        una fila por etapa ejecutada
    fact_contratos.parquet          resultado de cada contrato en cada ejecución
    fact_metricas.parquet           una fila por ejecución del monitor
    fact_metricas_segmento.parquet  error realizado por segmento ABC/XYZ
    fact_lazo.parquet               cada decisión de reentrenar, con sus razones
    dim_modelo.parquet              el registro de modelos, con estados y procedencia
    modelos/                        los pesos entrenados (.txt de LightGBM)
```

Todo en el mismo almacén que el resto: las métricas de operación son datos, y se consultan con
el mismo SQL. El cuadro de mando puede leer `fact_ejecuciones` sin ninguna integración especial.

## Para que se ejecute solo

Una entrada de `cron` semanal es suficiente a esta escala:

```cron
0 3 * * 1  cd /ruta/PROYECTO && /usr/bin/python3 operacion/orquestador.py >> operacion/registro.log 2>&1
```

El orquestador ya devuelve código de salida distinto de cero cuando falla, así que cualquier
supervisor —`cron` con notificación, `systemd`, un runner de CI— se entera sin más trabajo.

## Lo que sigue faltando

**El stock real.** Sin él la etapa de reposición calcula el nivel objetivo pero no el pedido.

**La decisión del encargado.** Sin registrar qué se pidió realmente frente a lo sugerido, el
monitor mide el error de predicción pero no si el sistema *sirve*.

**Umbrales calibrados.** Los de `monitor.py` y los de la puerta son razonables pero puestos a
mano. Con veinte o treinta ejecuciones registradas se calibran con el propio histórico de
`fact_metricas`, que es como debe hacerse.

**Contraste A/B en explotación.** La puerta compara métricas de validación, que describen el
pasado. Decidir entre dos modelos por lo que ocurre de verdad exige repartir tiendas entre ellos,
y eso requiere estar en explotación.
