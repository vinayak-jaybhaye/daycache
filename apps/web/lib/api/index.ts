// Central API export file for all API clients
export * from "./auth";
export {
  type UserProfileResponse,
  type UpdateProfileRequest,
  type SettingsResponse,
  type UpdateSettingsRequest,
  type AvatarUploadRequest,
  usersApi,
} from "./users";
export * from "./entries";
export { type TagCreate, type TagUpdate, tagsApi } from "./tags";
export * from "./collections";
export { type MoodCreate, type MoodUpdate, moodsApi } from "./moods";
export { type SearchResult, searchApi } from "./search";
export {
  aiApi,
  recallApi,
  reflectApi,
  type SummaryResponse,
  type RecallMessage,
  type ReflectMessage,
} from "./ai";
export { type DayEntryResponse, type DayListResponse, type ListDaysParams, daysApi } from "./days";
export { type PersonaResponse, personasApi } from "./personas";
export { type HealthResponse, healthApi } from "./health";
