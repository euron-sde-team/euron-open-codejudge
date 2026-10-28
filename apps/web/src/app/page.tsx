import { redirect } from "next/navigation";

/** The problems are the front door: signed in or not. */
export default function Home() {
  redirect("/problems");
}
