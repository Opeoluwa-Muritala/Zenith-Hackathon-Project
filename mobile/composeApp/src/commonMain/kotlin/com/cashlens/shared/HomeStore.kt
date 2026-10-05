package com.cashlens.shared

/** State for the shared home screen; monetary values are integer kobo. */
data class HomeState(
    val overview: LoadState<Overview> = LoadState.Loading,
    val insights: LoadState<List<Insight>> = LoadState.Loading,
)

/** User and lifecycle intents accepted by the shared home reducer. */
sealed interface HomeIntent {
    data object Refresh : HomeIntent
    data class OverviewLoaded(val value: Overview) : HomeIntent
    data class InsightsLoaded(val value: List<Insight>) : HomeIntent
    data class Failed(val reason: String) : HomeIntent
}

/** Pure MVI reducer shared by every KMP platform target. */
fun reduceHome(state: HomeState, intent: HomeIntent): HomeState = when (intent) {
    HomeIntent.Refresh -> HomeState()
    is HomeIntent.OverviewLoaded -> state.copy(overview = LoadState.Content(intent.value))
    is HomeIntent.InsightsLoaded -> state.copy(insights = if (intent.value.isEmpty()) LoadState.Empty else LoadState.Content(intent.value))
    is HomeIntent.Failed -> state.copy(overview = LoadState.Failed(intent.reason), insights = LoadState.Failed(intent.reason))
}
