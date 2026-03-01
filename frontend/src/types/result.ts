export type ResultType = "place" | "event"

export interface ResultMeta {
  city: string
  keywords: string[]
  rows_returned: number
}

export interface ScoreBreakdown {
  similarity: number
  popularity: number
  weather: number
  urgency: number
}

export interface ResultRow {
  name: string
  type: ResultType

  lat: number
  lon: number

  address: string
  description: string

  score: number
  breakdown: ScoreBreakdown
}

export interface SearchResults {
  meta: ResultMeta
  rows: ResultRow[]
}