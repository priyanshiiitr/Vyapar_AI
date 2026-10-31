import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Card, CardTitle } from "@/components/ui/card";

export function InvoicesPage() {
  const { data } = useQuery({ queryKey: ["invoices"], queryFn: () => api.invoices() });
  return (
    <div className="space-y-4 animate-rise">
      <h2 className="font-display text-4xl">Invoices</h2>
      <Card>
        <CardTitle>Ledger invoices</CardTitle>
        <div className="mt-4 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-[var(--muted)]">
              <tr>
                <th className="py-2">Invoice</th>
                <th>Customer</th>
                <th>Amount</th>
                <th>Paid</th>
                <th>Outstanding</th>
                <th>Status</th>
                <th>Due</th>
              </tr>
            </thead>
            <tbody>
              {(data?.invoices || []).map((i: any) => (
                <tr key={i.invoice_id} className="border-t border-[var(--line)]">
                  <td className="py-3 font-semibold">{i.invoice_id}</td>
                  <td>{i.customer}</td>
                  <td>{i.amount}</td>
                  <td>{i.paid}</td>
                  <td>{i.outstanding}</td>
                  <td>
                    <span className="rounded-full bg-teal-50 px-2 py-1 text-xs text-teal-800">{i.status}</span>
                  </td>
                  <td>{i.due_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
