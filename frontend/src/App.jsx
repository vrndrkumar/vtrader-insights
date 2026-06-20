import { BrowserRouter, Routes, Route } from "react-router-dom";
import { JobProvider } from "./lib/JobContext";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import StockReport from "./pages/StockReport";
import FullReport from "./pages/FullReport";

export default function App() {
  return (
    <JobProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="stock/:symbolCode" element={<StockReport />} />
            <Route path="report" element={<FullReport />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </JobProvider>
  );
}
