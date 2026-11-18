import { NavLink, Route, Routes } from "react-router";
import { ClaimPage } from "./ClaimPage";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

export function App() {
  return (
    <>
      <header className="header">
        <NavLink to="/" className="brand">
          UnderCover <span className="tagline">Claims desk</span>
        </NavLink>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Queue
          </NavLink>
          <NavLink to="/instructions">Instructions</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Queue />} />
          <Route path="/claims/:claimId" element={<ClaimPage />} />
          <Route path="/instructions" element={<Instructions />} />
        </Routes>
      </main>
    </>
  );
}
