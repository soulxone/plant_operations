"""Label Printer — Generate ZPL and PDF labels for pallets and load tags.

Supports:
  - ZPL: Direct to Zebra thermal printer (4"x6" pallet tags, 4"x8" load tags)
  - PDF: Browser-printable PDF via Frappe's HTML-to-PDF
"""
import frappe
from frappe.utils import today, now_datetime


def generate_pallet_label(pallet_name, mode="pdf"):
    """Generate a pallet tag label.

    Returns: ZPL string (mode='zpl') or HTML string for PDF rendering (mode='pdf')
    """
    pallet = frappe.get_doc("Pallet", pallet_name)

    if mode == "zpl":
        return {"zpl": _pallet_zpl(pallet), "format": "zpl"}
    else:
        return {"html": _pallet_html(pallet), "format": "html"}


def generate_load_label(load_tag_name, mode="pdf"):
    """Generate a load tag label."""
    load = frappe.get_doc("Load Tag", load_tag_name)

    if mode == "zpl":
        return {"zpl": _load_zpl(load), "format": "zpl"}
    else:
        return {"html": _load_html(load), "format": "html"}


# ─── ZPL Templates ───────────────────────────────────────────────────────────

def _pallet_zpl(p):
    """4x6 inch pallet tag in ZPL (Zebra Programming Language)."""
    barcode_data = p.barcode or p.name
    return f"""^XA
^CF0,30
^FO50,30^FD{p.name}^FS
^CF0,20
^FO50,70^FDPALLET TAG^FS
^FO50,100^GB700,2,2^FS
^BY3,2,120
^FO80,120^BC,,120,Y,N^FD{barcode_data}^FS
^CF0,24
^FO50,280^FDCustomer: {(p.customer or '—')[:30]}^FS
^FO50,310^FDItem: {(p.item_name or '—')[:35]}^FS
^FO50,340^FDQty: {p.quantity or 0} pcs^FS
^FO50,370^FDWeight: {p.weight_lbs or 0:.0f} lbs^FS
^FO50,400^FDSO: {p.sales_order or '—'}^FS
^FO50,430^FDZone: {p.zone or '—'}^FS
^FO50,470^GB700,2,2^FS
^CF0,18
^FO50,480^FDPrinted: {today()}^FS
^FO400,480^FDBy: {frappe.session.user[:20]}^FS
^XZ"""


def _load_zpl(lt):
    """4x8 inch load tag in ZPL."""
    barcode_data = lt.name
    return f"""^XA
^CF0,36
^FO50,30^FD{lt.name}^FS
^CF0,22
^FO50,75^FDLOAD TAG^FS
^FO50,105^GB700,3,3^FS
^BY3,2,100
^FO80,120^BC,,100,Y,N^FD{barcode_data}^FS
^CF0,28
^FO50,260^FDTrailer: {lt.trailer_number or '—'}^FS
^FO400,260^FDSeal: {lt.seal_number or '—'}^FS
^FO50,300^FDCarrier: {(lt.carrier or '—')[:25]}^FS
^FO400,300^FDDriver: {(lt.driver_name or '—')[:20]}^FS
^FO50,340^GB700,2,2^FS
^CF0,24
^FO50,355^FDDESTINATION^FS
^CF0,28
^FO50,385^FD{(lt.destination_customer or '—')[:35]}^FS
^CF0,20
^FO50,420^FD{(lt.destination_address or '—')[:45]}^FS
^FO50,455^GB700,2,2^FS
^CF0,26
^FO50,470^FDPallets: {lt.total_pallets or 0}^FS
^FO250,470^FDPieces: {lt.total_pieces or 0}^FS
^FO450,470^FDWeight: {lt.total_weight or 0:.0f} lbs^FS
^FO50,510^FDBOL: {lt.bol_number or '—'}^FS
^FO400,510^FDShip: {lt.ship_date or today()}^FS
^FO50,550^GB700,2,2^FS
^CF0,18
^FO50,560^FDPrinted: {today()} | Status: {lt.status}^FS
^XZ"""


# ─── HTML/PDF Templates ──────────────────────────────────────────────────────

def _pallet_html(p):
    """4x6 inch pallet tag as HTML (for PDF printing)."""
    barcode_data = p.barcode or p.name
    return f"""<!DOCTYPE html>
<html><head>
<style>
  @page {{ size: 4in 6in; margin: 0.2in; }}
  body {{ font-family: Arial, sans-serif; font-size: 12px; color: #000; }}
  .tag {{ border: 2px solid #000; padding: 12px; height: 5.4in; position: relative; }}
  .tag-id {{ font-size: 24px; font-weight: 900; letter-spacing: 2px; }}
  .tag-type {{ font-size: 10px; color: #666; letter-spacing: 3px; text-transform: uppercase; }}
  .divider {{ border-top: 2px solid #000; margin: 8px 0; }}
  .barcode {{ text-align: center; margin: 12px 0; }}
  .barcode img {{ max-width: 100%; height: 80px; }}
  .barcode-text {{ font-family: monospace; font-size: 14px; letter-spacing: 3px; margin-top: 4px; }}
  .field {{ margin: 4px 0; }}
  .field .lbl {{ font-size: 9px; color: #888; text-transform: uppercase; }}
  .field .val {{ font-size: 14px; font-weight: 700; }}
  .footer {{ position: absolute; bottom: 8px; left: 12px; right: 12px; font-size: 9px; color: #999; }}
</style>
</head><body>
<div class="tag">
  <div class="tag-id">{p.name}</div>
  <div class="tag-type">Pallet Tag</div>
  <div class="divider"></div>
  <div class="barcode">
    <div class="barcode-text">{barcode_data}</div>
  </div>
  <div class="divider"></div>
  <div class="field"><div class="lbl">Customer</div><div class="val">{p.customer or '—'}</div></div>
  <div class="field"><div class="lbl">Item</div><div class="val">{p.item_name or '—'}</div></div>
  <div style="display:flex;gap:20px;">
    <div class="field" style="flex:1;"><div class="lbl">Qty</div><div class="val">{p.quantity or 0}</div></div>
    <div class="field" style="flex:1;"><div class="lbl">Weight</div><div class="val">{p.weight_lbs or 0:.0f} lbs</div></div>
  </div>
  <div class="field"><div class="lbl">Sales Order</div><div class="val">{p.sales_order or '—'}</div></div>
  <div class="field"><div class="lbl">Zone</div><div class="val">{p.zone or '—'}</div></div>
  <div class="footer">Printed {today()} | {p.status}</div>
</div>
</body></html>"""


def _load_html(lt):
    """4x8 inch load tag as HTML (for PDF printing)."""
    # Build pallet list
    pallet_rows = ""
    for i, row in enumerate(lt.load_pallets or []):
        pallet_rows += f"<tr><td>{i+1}</td><td>{row.pallet_id or row.pallet}</td><td>{row.quantity or 0}</td><td>{row.weight_lbs or 0:.0f}</td></tr>"

    return f"""<!DOCTYPE html>
<html><head>
<style>
  @page {{ size: 4in 8in; margin: 0.2in; }}
  body {{ font-family: Arial, sans-serif; font-size: 11px; color: #000; }}
  .tag {{ border: 3px solid #000; padding: 12px; }}
  .tag-id {{ font-size: 28px; font-weight: 900; letter-spacing: 2px; }}
  .tag-type {{ font-size: 11px; color: #666; letter-spacing: 3px; text-transform: uppercase; }}
  .divider {{ border-top: 2px solid #000; margin: 6px 0; }}
  .barcode-text {{ font-family: monospace; font-size: 16px; letter-spacing: 3px; text-align: center; margin: 8px 0; }}
  .row {{ display: flex; gap: 12px; margin: 3px 0; }}
  .row .lbl {{ font-size: 8px; color: #888; text-transform: uppercase; }}
  .row .val {{ font-size: 13px; font-weight: 700; }}
  .dest {{ background: #f0f0f0; padding: 8px; border-radius: 4px; margin: 6px 0; }}
  .dest .dest-title {{ font-size: 8px; letter-spacing: 2px; color: #888; text-transform: uppercase; }}
  .dest .dest-name {{ font-size: 18px; font-weight: 900; }}
  .dest .dest-addr {{ font-size: 11px; color: #444; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 10px; margin-top: 4px; }}
  th {{ background: #000; color: #fff; padding: 3px 6px; text-align: left; font-size: 8px; letter-spacing: 1px; }}
  td {{ padding: 2px 6px; border-bottom: 1px solid #ddd; }}
  .summary {{ display: flex; gap: 8px; margin: 6px 0; }}
  .summary .box {{ flex: 1; text-align: center; border: 1px solid #000; padding: 4px; }}
  .summary .box .num {{ font-size: 20px; font-weight: 900; }}
  .summary .box .label {{ font-size: 7px; letter-spacing: 1px; text-transform: uppercase; }}
  .footer {{ font-size: 8px; color: #999; margin-top: 6px; }}
</style>
</head><body>
<div class="tag">
  <div class="tag-id">{lt.name}</div>
  <div class="tag-type">Load Tag</div>
  <div class="divider"></div>
  <div class="barcode-text">{lt.name}</div>
  <div class="divider"></div>
  <div class="row">
    <div style="flex:1;"><div class="lbl">Trailer</div><div class="val">{lt.trailer_number or '—'}</div></div>
    <div style="flex:1;"><div class="lbl">Seal</div><div class="val">{lt.seal_number or '—'}</div></div>
    <div style="flex:1;"><div class="lbl">BOL</div><div class="val">{lt.bol_number or '—'}</div></div>
  </div>
  <div class="row">
    <div style="flex:1;"><div class="lbl">Carrier</div><div class="val">{lt.carrier or '—'}</div></div>
    <div style="flex:1;"><div class="lbl">Driver</div><div class="val">{lt.driver_name or '—'}</div></div>
    <div style="flex:1;"><div class="lbl">Ship Date</div><div class="val">{lt.ship_date or '—'}</div></div>
  </div>
  <div class="dest">
    <div class="dest-title">Destination</div>
    <div class="dest-name">{lt.destination_customer or '—'}</div>
    <div class="dest-addr">{lt.destination_address or ''}</div>
  </div>
  <div class="summary">
    <div class="box"><div class="num">{lt.total_pallets or 0}</div><div class="label">Pallets</div></div>
    <div class="box"><div class="num">{lt.total_pieces or 0}</div><div class="label">Pieces</div></div>
    <div class="box"><div class="num">{lt.total_weight or 0:.0f}</div><div class="label">Lbs</div></div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Pallet ID</th><th>Qty</th><th>Weight</th></tr></thead>
    <tbody>{pallet_rows}</tbody>
  </table>
  <div class="footer">Printed {today()} | Status: {lt.status}</div>
</div>
</body></html>"""
