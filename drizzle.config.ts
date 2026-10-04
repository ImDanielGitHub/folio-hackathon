import {defineConfig} from 'drizzle-kit';
export default defineConfig({out:'./drizzle',schema:'./apps/edge/db/schema.ts',dialect:'sqlite'});
