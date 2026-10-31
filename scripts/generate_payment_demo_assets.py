"""Generate customer payment proof PNGs + matching bank txn CSVs for demo."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"


def make_proof(
    path: Path,
    *,
    payer: str,
    payee: str,
    amount: str,
    utr: str,
    invoice_ref: str,
    note: str,
) -> None:
    img = Image.new("RGB", (720, 1100), "#0b141a")
    d = ImageDraw.Draw(img)
    try:
        font_lg = ImageFont.truetype("arial.ttf", 28)
        font_md = ImageFont.truetype("arial.ttf", 22)
        font_sm = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font_lg = font_md = font_sm = ImageFont.load_default()

    d.rounded_rectangle((40, 40, 680, 1060), radius=28, fill="#1f2c34")
    d.ellipse((300, 70, 420, 190), fill="#00a884")
    d.text((348, 110), "OK", fill="white", font=font_lg)
    d.text((180, 220), "Payment Successful", fill="#e8f5e9", font=font_lg)
    d.text((220, 270), amount, fill="#ffffff", font=font_lg)

    today = date.today().isoformat()
    lines = [
        ("To", payee),
        ("From", payer),
        ("Amount", amount),
        ("UTR / Ref", utr),
        ("Invoice", invoice_ref),
        ("Date", today),
        ("Mode", "UPI"),
        ("Status", "SUCCESS (synthetic demo)"),
        ("Note", note),
    ]
    y = 340
    for key, value in lines:
        d.text((80, y), key, fill="#90a4ae", font=font_sm)
        d.text((80, y + 28), value, fill="#ffffff", font=font_md)
        y += 80

    d.text((80, 980), "SYNTHETIC TEST DATA - not a real bank receipt", fill="#ffcc80", font=font_sm)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print("wrote", path)


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    make_proof(
        SAMPLES / "payment_proof_R104_ABC_Stores.png",
        payer="ABC Stores · 9999900001",
        payee="Demo Merchant (Vyapar AI)",
        amount="Rs 15,000.00",
        utr="UPI429184736201",
        invoice_ref="R-104",
        note="Clearing remaining balance for R-104",
    )
    make_proof(
        SAMPLES / "payment_proof_SBH_Sharma_Electrical.png",
        payer="Sharma Electrical Works · 9000000002",
        payee="Shree Balaji Electricals (demo)",
        amount="Rs 15,000.00",
        utr="UPI518273645091",
        invoice_ref="SBH/26-27/104",
        note="Balance due for SBH/26-27/104",
    )

    (SAMPLES / "txn_r104_clear.csv").write_text(
        "transaction_id,reference,amount,transaction_date,customer_name,notes\n"
        f"TXN-R104-CLEAR,R-104,15000,{today},ABC Stores,"
        "Customer UPI UPI429184736201 remaining balance\n",
        encoding="utf-8",
    )
    (SAMPLES / "txn_sbh_104_clear.csv").write_text(
        "transaction_id,reference,amount,transaction_date,customer_name,notes\n"
        f"TXN-SBH-104-CLEAR,SBH/26-27/104,15000,{today},Sharma Electrical Works,"
        "Customer UPI UPI518273645091 balance due\n",
        encoding="utf-8",
    )

    make_proof(
        SAMPLES / "payment_proof_R106_Kumar_Mart.png",
        payer="Kumar Mart · 9999900003",
        payee="Demo Merchant (Vyapar AI)",
        amount="Rs 18,000.00",
        utr="UPI62738491502",
        invoice_ref="R-106",
        note="Full payment for invoice R-106 monthly supplies",
    )
    (SAMPLES / "txn_r106_clear.csv").write_text(
        "transaction_id,reference,amount,transaction_date,customer_name,notes\n"
        f"TXN-R106-CLEAR,R-106,18000,{today},Kumar Mart,"
        "Customer UPI UPI62738491502 full payment R-106\n",
        encoding="utf-8",
    )
    print("wrote CSVs for", today)


if __name__ == "__main__":
    main()
