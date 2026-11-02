# Contrato — depotru-inbox (pedidos por despachar)

> **Estado:** rebanada B implementada como dominio + adaptador en memoria
> (`src/modules/inbox/`). **Falta** el adaptador real contra las tablas, el
> consumidor de Magento y la pantalla de despacho.
> **Alcance:** define qué es un pedido despachable, cuándo sale un viaje, y qué
> se rechaza. No define precios de flete (rebanada A) ni recogida en bodega
> (rebanada C).

---

## 1. Qué entra a la bandeja

Un pedido de Magento se convierte en carga con cuatro datos: `magento_order_id`,
`weight_kg`, ciudad/departamento de destino y sede (`neiva` | `florencia`).

Se **rechaza** —y se reporta, no se corrige— cuando:

| Caso | Motivo |
|---|---|
| Sin peso, `0`, negativo o no numérico | el camión se planea con ese número; suponerlo mueve carga que nadie paga |
| Peso > 40.000 kg en una sola orden | no es una entrega, es un error de dato |
| Sin ciudad de destino | no hay tarifa posible (rebanada A falla cerrada igual) |
| Sede desconocida | R9: v1 solo Neiva y Florencia |
| Sin `magento_order_id` | no hay idempotencia posible |

El peso se guarda como decimal de punto fijo (`DECIMAL(12,3)`), nunca `float`:
un float reordenado cambia el total del viaje por centésimas que después no
cuadran contra la factura.

## 2. Idempotencia

La misma orden puede llegar dos veces (reintento del consumidor, replay de
cola). Mismo id + **misma carga** ⇒ no se escribe nada. Mismo id + **carga
distinta** (peso, destino, sede, fecha) ⇒ `DuplicateOrderConflict` y no se
toca la fila: un pedido ya asignado a un viaje no puede cambiar de peso sin que
alguien lo vea.

## 3. Cuándo sale un viaje

La sede nunca se mezcla: un camión de Florencia no recoge en Neiva.

1. **Dedicado** — una orden cuyo peso ya alcanza el umbral sale sola de
   inmediato, en el vehículo más pequeño que la cargue.
2. **Umbral** — las órdenes pendientes se acumulan en FIFO hasta llegar al
   umbral; ahí sale el viaje, otra vez en el vehículo más pequeño que quepa
   (el camión grande queda libre).
3. **Espera máxima** — si el pedido más viejo lleva más de N horas esperando,
   sale con los que ya cumplieron la espera. Los jóvenes siguen esperando
   camión lleno; no se les cuelga a una van por conveniencia.
4. **Bloqueado** — una orden que excede la capacidad del vehículo más grande de
   su sede se reporta y **no** viaja: sobrecargar no es una opción y bloquear a
   los demás tampoco, así que el resto del lote sigue su curso.

`plan_dispatch` es una función pura: mismas entradas ⇒ mismo plan, sin reloj ni
I/O, para que el plan se pueda auditar y reproducir.

## 4. El agente de sistema

`run_dispatch` es el único escritor de viajes hoy. Firma cada viaje con
`created_by = 'system:dispatch'` y crea el viaje en estado `planned`; asignar
órdenes y crear el viaje ocurren juntos. Correrlo dos veces sin pedidos nuevos
no crea nada (las órdenes ya están `assigned`).

## 5. Números candidatos — requieren confirmación

| Parámetro | Valor actual | Quién confirma |
|---|---|---|
| `threshold_kg` | 6.000 kg | despacho / ventas |
| `max_wait_hours` | 24 h | despacho |

Están en `DispatchPolicy`, no en la base: cambiarlos no requiere DDL ni
despliegue de esquema, y el valor vigente debe quedar escrito antes de encender
la bandeja en producción.

## 6. Fuera de alcance

- Consumidor Magento → bandeja (rebanada B2).
- Adaptador SQL de `InboxRepository` (el DDL está en
  `data/sql/inbox_dispatch_tables.sql`).
- Pantalla de despacho y reasignación manual de vehículo.
- Flete en el total del carro (rebanada A, ya calculado) y recogida en bodega
  (rebanada C).
