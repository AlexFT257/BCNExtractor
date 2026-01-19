# Web Service

La **BCN** ofrece un [servicio web](https://www.bcn.cl/leychile/consulta/legislacion_abierta_web_service) para desarrolladores donde permite descargar datos con distintas aplicaciones mediante XML, entre los servicios que son mas utiles se encuentran:

- Obtiene los metadatos de una norma y el texto de encabezado
- Obtiene el XML completo de la version actualizada de una norma. (**Norma completa**)
- Normas seleccionadas por una institucion en convenio con la BCN. (**Normas por institucion**)

## Estructura de una norma

Las normas se componen de varias partes, Encabezado, estructura, promulgacion y anexos.

## Servicios utiles

### Metadatos de una norma y encabezado

Consulta por los metadatos de una norma (tipo de norma, palabras claves, organismo, materia) más su encabezado.

[https://www.leychile.cl/Consulta/obtxml?opt=4546&idNorma=206396](https://www.leychile.cl/Consulta/obtxml?opt=4546&idNorma=206396)

Como [parámetro](http://es.wikipedia.org/wiki/Argumento_%28inform%C3%A1tica%29) deberá colocar el número del identificador único de la norma. Para obtener este identificador deberá obtenerlo buscando por el número de la ley (en la [búsqueda simple](https://www.leychile.cl/Consulta)) y se encuentra en datos / identificadores / Norma ID ([ver ejemplo](https://www.leychile.cl/Navegar?idLey=19628&dt=open))

Ejemplo:

```xml
<Norma xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.leychile.cl/esquemas" xsi:schemaLocation="http://www.leychile.cl/esquemas http://www.leychile.cl/esquemas/EsquemaIntercambioNorma-v1-0.xsd" normaId="206396" esTratado="no tratado" fechaVersion="2022-12-30" SchemaVersion="1.0" derogado="no derogado">
  <Identificador fechaPromulgacion="2002-12-09" fechaPublicacion="2003-01-04">
    <TiposNumeros>
      <TipoNumero>
        <Tipo>Ley</Tipo>
        <Numero>19846</Numero>
      </TipoNumero>
    </TiposNumeros>
    <Organismos>
      <Organismo>MINISTERIO SECRETARÍA GENERAL DE GOBIERNO</Organismo>
    </Organismos>
  </Identificador>
  <Metadatos>
    <TituloNorma>SOBRE CALIFICACION DE LA PRODUCCION CINEMATOGRAFICA.</TituloNorma>
    <Materias>
      <Materia>Calificación de la Producción Cinematográfica </Materia>
      <Materia>Consejo de Calificación Cinematográfica </Materia>
      <Materia>Ley no. 19.846</Materia>
    </Materias>
    <NombresUsoComun>
      <NombreUsoComun>CALIFICACION CINEMATOGRAFICA</NombreUsoComun>
    </NombresUsoComun>

    <IdentificacionFuente>Diario Oficial</IdentificacionFuente>
    <NumeroFuente>37450</NumeroFuente>
  </Metadatos>
  <Encabezado fechaVersion="2003-01-04" derogado="no derogado">
    <Texto>SOBRE CALIFICACION DE LA PRODUCCION CINEMATOGRAFICA
     Teniendo presente que el H. Congreso Nacional ha dado
su aprobación al siguiente

     Proyecto de ley
     </Texto>
  </Encabezado>
...
```

### XML completo de version actualizada de una norma

Última versión de cualquier norma (leyes, decretos, tratados, DL, DFL, resoluciones, etc.)

[https://www.leychile.cl/Consulta/obtxml?opt=7&idNorma=206396](https://www.leychile.cl/Consulta/obtxml?opt=7&idNorma=206396)

Como [parámetro](http://es.wikipedia.org/wiki/Argumento_%28inform%C3%A1tica%29) deberá colocar el número único de identificación de la norma o número BCN (no confundir con número de la ley), el que puede obtener buscando por el número de la ley (en la [búsqueda simple](https://www.leychile.cl/Consulta)) y se encuentra en datos / identificadores / Norma ID ([ver ejemplo](https://www.leychile.cl/Navegar?idLey=19628&dt=open))

### Normas seleccionadas por [[instituciones]]

Consulta por las normas seleccionadas por una determinada institución

[https://www.leychile.cl/Consulta/obtxml?opt=6&idCategoria=17](https://www.leychile.cl/Consulta/obtxml?opt=6&idCategoria=17&down=True)

En el [parámetro](http://es.wikipedia.org/wiki/Argumento_%28inform%C3%A1tica%29) idCategoria deberá colocar el número del convenio, el que puede obtener siguiendo los siguientes pasos:  
1.- Visitar la siguiente página [https://www.leychile.cl/Consulta/agrupadores?tipCat=1&lxi=t](https://www.leychile.cl/Consulta/agrupadores?tipCat=1&lxi=t)  
2.- Buscar la institución a consultar y descargar el XML del convenio  
3.- Obtener el valor del atributo id_categoria desde el elemento NORMAS_CONVENIO

# Tipos de normas

En el Web Service de la BCN existen distinciones entre los tipos de normas que hay (decretos, leyes, decretos con fuerza de ley, etc.), estos se encuentra en el XML de las normas guardado como:

```xml
<Grupo id_grupo="153">Decretos</Grupo>
```

**Sin embargo**, también existe otra clasificacion o forma de clasificacion de las normas en el Web Service, especificamente el `<Tipos_Numeros>`:

```xml
<TIPOS_NUMEROS>
	<TIPO_NUMERO>
		<TIPO>XX2</TIPO>
		<NUMERO>179</NUMERO>
		<DESCRIPCION>Decreto</DESCRIPCION>
		<ABREVIACION>DTO</ABREVIACION>
		<COMPUESTO>DTO-179</COMPUESTO>
	</TIPO_NUMERO>
</TIPOS_NUMEROS>
```

La primera forma de clasificacion (de ahora en adelante <Grupo>), solo se encuentra en las respuestas al endpoint de **Normas por institucion** y el `id_grupo` no atiende a ningun otro endpoint e incluso el id_grupo cambia por insitucion para los mismos tipos de norma, es decir que los ids de un tipo de norma pueden ser diferentes dependiendo de la institucion.

**La segunda forma de clasificacion (de ahora en adelante <TIPO_NUMERO>)**, se encuentra tanto en las respuestas al endpoint de **Norma completa** como en el endpoint de **Normas por institucion**, y es la forma de clasificacion que se utiliza para identificar un tipo de norma de manera única en el Web Service. Pero esta forma no es consistente con el endpoint de **Norma Completa**

Por ejemplo:

### Norma Completa

```xml
<TiposNumeros>
  <TipoNumero>
    <Tipo>Ley</Tipo>
    <Numero>19846</Numero>
  </TipoNumero>
</TiposNumeros>
```

### Normas por institucion

```xml
<TIPOS_NUMEROS>
	<TIPO_NUMERO>
		<TIPO>XX2</TIPO>
		<NUMERO>179</NUMERO>
		<DESCRIPCION>Decreto</DESCRIPCION>
		<ABREVIACION>DTO</ABREVIACION>
		<COMPUESTO>DTO-179</COMPUESTO>
	</TIPO_NUMERO>
</TIPOS_NUMEROS>
```

## Problema-Solucion

En resumen el Web Service de la BCN no pose una forma de clasificacion de normas consistentes en todos los endpoints, por lo que es necesario utilizar la forma de clasificacion <TIPO_NUMERO> para identificar un tipo de norma de manera única en el Web Service.

Es por esto que se creo el `TiposNormasManager` para manejar la forma de clasificacion <TIPO_NUMERO> y poder identificar un tipo de norma de manera única en el Web Service.

# Instituciones

La BCN, a partir de su Base de Datos Legal, provee a [instituciones](https://www.bcn.cl/leychile/consulta/agrupadores?tipCat=1&lxi=t) públicas y privadas acceso, vía digital, a la normativa siempre actualizada de su ámbito de acción.
