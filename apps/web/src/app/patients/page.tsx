import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Search, UserCircle, ArrowUpDown } from "lucide-react";

interface SortHeaderProps {
  active: boolean;
  href: string;
  label: string;
}

function SortHeader({ active, href, label }: SortHeaderProps) {
  return (
    <Link href={href} className="group flex items-center transition-colors hover:text-foreground">
      {label}
      <ArrowUpDown
        className={`ml-2 h-3 w-3 ${active ? "text-blue-500 opacity-100" : "opacity-30 group-hover:opacity-100"}`}
      />
    </Link>
  );
}

async function searchPatients(query: string, gender: string, dobStart: string, dobEnd: string, page: number = 1, sort: string = "name", order: string = "asc") {
  const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
  const url = new URL(`${apiUrl}/patients`);
  if (query) url.searchParams.append("q", query);
  if (gender) url.searchParams.append("gender", gender);
  if (dobStart) url.searchParams.append("dob_start", dobStart);
  if (dobEnd) url.searchParams.append("dob_end", dobEnd);
  url.searchParams.append("page", page.toString());
  url.searchParams.append("sort", sort);
  url.searchParams.append("order", order);
  
  try {
    const res = await fetch(url.toString(), { cache: 'no-store' });
    if (!res.ok) throw new Error("Failed to search");
    const data = await res.json();
    return data;
  } catch (error) {
    console.error("Search API Error:", error);
    return { data: [], pagination: { total: 0, page: 1, limit: 20, total_pages: 1 } };
  }
}

export default async function PatientsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; gender?: string; dob_start?: string; dob_end?: string; page?: string; sort?: string; order?: string }>
}) {
  const resolvedParams = await searchParams;
  const q = resolvedParams.q || "";
  const gender = resolvedParams.gender || "";
  const dobStart = resolvedParams.dob_start || "";
  const dobEnd = resolvedParams.dob_end || "";
  const page = resolvedParams.page ? parseInt(resolvedParams.page) : 1;
  const sort = resolvedParams.sort || "name";
  const order = resolvedParams.order || "asc";
  
  const { data: patients, pagination } = await searchPatients(q, gender, dobStart, dobEnd, page, sort, order);

  const filterParams = `&q=${encodeURIComponent(q)}&gender=${encodeURIComponent(gender)}&dob_start=${encodeURIComponent(dobStart)}&dob_end=${encodeURIComponent(dobEnd)}`;

  const getSortLink = (field: string) => {
    const nextOrder = sort === field && order === "asc" ? "desc" : "asc";
    return `/patients?page=1${filterParams}&sort=${field}&order=${nextOrder}`;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Patient Registry</h2>
          <p className="text-muted-foreground mt-1">Search and view synthetic patient records.</p>
        </div>
        
        <form className="flex flex-wrap items-center gap-2 xl:justify-end">
          <Input 
            type="search" 
            name="q"
            defaultValue={q}
            placeholder="Name or ID..." 
            className="bg-background border-input w-40"
          />
          <select name="gender" defaultValue={gender} className="flex h-10 w-32 items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
            <option value="">All Genders</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            DOB:
            <Input type="date" name="dob_start" defaultValue={dobStart} className="bg-background border-input w-36" title="Min DOB" />
            <span>-</span>
            <Input type="date" name="dob_end" defaultValue={dobEnd} className="bg-background border-input w-36" title="Max DOB" />
          </div>
          <Button type="submit" variant="secondary">
            <Search className="h-4 w-4 mr-2" />
            Search
          </Button>
        </form>
      </div>

      <div className="rounded-md border border-border bg-card/50">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead><SortHeader active={sort === "id"} href={getSortLink("id")} label="ID" /></TableHead>
              <TableHead><SortHeader active={sort === "name"} href={getSortLink("name")} label="Name" /></TableHead>
              <TableHead><SortHeader active={sort === "gender"} href={getSortLink("gender")} label="Gender" /></TableHead>
              <TableHead><SortHeader active={sort === "birthDate"} href={getSortLink("birthDate")} label="DOB" /></TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {patients.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center h-32 text-muted-foreground">
                  No patients found.
                </TableCell>
              </TableRow>
            ) : (
              patients.map((p: any) => (
                <TableRow key={p.id} className="border-border hover:bg-muted/50">
                  <TableCell className="font-medium text-muted-foreground">
                    {p.id.replace('Patient/', '')}
                  </TableCell>
                  <TableCell>{p.name}</TableCell>
                  <TableCell className="capitalize">{p.gender}</TableCell>
                  <TableCell>{p.birthDate}</TableCell>
                  <TableCell className="text-right">
                    <Link href={`/patients/${p.id.replace('Patient/', '')}`}>
                      <Button variant="ghost" size="sm">
                        <UserCircle className="h-4 w-4 mr-2" />
                        View 360
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Controls */}
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {((pagination.page - 1) * pagination.limit) + 1} to {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total} patients
          </p>
          <div className="flex gap-2">
            <Link href={`/patients?page=${Math.max(1, pagination.page - 1)}${filterParams}&sort=${sort}&order=${order}`} className={pagination.page <= 1 ? "pointer-events-none opacity-50" : ""}>
              <Button variant="outline" size="sm" disabled={pagination.page <= 1}>Previous</Button>
            </Link>
            <Link href={`/patients?page=${Math.min(pagination.total_pages, pagination.page + 1)}${filterParams}&sort=${sort}&order=${order}`} className={pagination.page >= pagination.total_pages ? "pointer-events-none opacity-50" : ""}>
              <Button variant="outline" size="sm" disabled={pagination.page >= pagination.total_pages}>Next</Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
