# Tema de scriptorium: Universidad de La Habana

Tema `uh` para documentos renderizados con scriptorium (`repos/scriptorium`). Extiende el tema `report` y aplica la identidad visual de la UH descrita en `../README.md`: guinda y oro, titulares en Source Serif 4, portada con el escudo y la wordmark institucional. Cada capítulo (`#`) empieza en página nueva.

## Uso

El tema vive en `repos/scriptorium/themes/uh/`, así que se nombra directamente:

```yaml
theme: uh
```

La portada usa el componente `cover` con estos atributos:

```markdown
::: cover {title="CAIA" org="Universidad de La Habana" org_sub="Propuesta a la Rectora" date="Septiembre de 2026" edition="Borrador"}
Subtítulo del documento
:::
```

## Archivos

- `theme.yml`: hereda de `report`, fija los colores y las fuentes.
- `styles.css`: paleta, titulares, tablas, portada y salto de página por capítulo.
- `masters/cover.html`: portada con el escudo incrustado como data URI, porque los `.jpg` no se versionan en el vault.
- `assets/texto-oro.svg`: wordmark en oro para fondo guinda.
