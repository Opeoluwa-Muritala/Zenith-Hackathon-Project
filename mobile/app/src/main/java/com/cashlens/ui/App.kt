package com.cashlens.ui
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
enum class Tab(val label:String){Home("Home"),Transactions("Transactions"),Bills("Bills"),Insights("Insights"),Consent("Consent")}
sealed interface UiState<out T>{data object Loading:UiState<Nothing>;data class Ready<T>(val data:T):UiState<T>;data class Error(val message:String):UiState<Nothing>;data object Empty:UiState<Nothing>}
@Composable fun CashlensApp(){var tab by remember{mutableStateOf(Tab.Home)};Scaffold(bottomBar={NavigationBar{Tab.entries.forEach{item->NavigationBarItem(selected=tab==item,onClick={tab=item},icon={Icon(Icons.Default.Info,null)},label={Text(item.label)})}}}){padding->Box(Modifier.padding(padding)){when(tab){Tab.Home->Home();Tab.Transactions->StateScreen("No transactions yet","Link or upload an account to begin.");Tab.Bills->Bills();Tab.Insights->Insights();Tab.Consent->Consent()}}}}
@Composable fun Home(){LazyColumn(contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){item{Text("Good afternoon",style=MaterialTheme.typography.headlineMedium)};item{MetricCard("Safe to spend today","₦0.00","Connect accounts to calculate your daily guide")};item{Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){MetricCard("Income","₦0.00",Modifier.weight(1f));MetricCard("Spend","₦0.00",Modifier.weight(1f))}};item{MetricCard("Total balance","₦0.00")};item{Text("Top insights",style=MaterialTheme.typography.titleLarge)};item{StateScreen("Insights will appear here","Sync an account to run all twelve checks.")}}}
@Composable fun MetricCard(label:String,value:String,modifier:Modifier=Modifier,detail:String?=null){Card(modifier.fillMaxWidth()){Column(Modifier.padding(16.dp)){Text(label);Text(value,style=MaterialTheme.typography.headlineMedium);detail?.let{Text(it)}}}}
@Composable fun Insights(){val modules=listOf("Cashflow and liquidity","Subscriptions and leaks","Behaviour and blind spots","Wealth acceleration");LazyColumn(contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){item{Text("Insights",style=MaterialTheme.typography.headlineMedium)};items(modules){Card(Modifier.fillMaxWidth()){Column(Modifier.padding(16.dp)){Text(it,style=MaterialTheme.typography.titleMedium);Text("No active insights")}}}}}
@Composable fun Bills(){Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){Text("Subscriptions and bills",style=MaterialTheme.typography.headlineMedium);StateScreen("No recurring charges yet","Sync an account to detect bills and subscriptions.")}}
@Composable fun Consent(){Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){Text("Consent manager",style=MaterialTheme.typography.headlineMedium);StateScreen("No active consent","Connect a bank or use demo accounts.");Button(onClick={},modifier=Modifier.fillMaxWidth().heightIn(min=48.dp)){Text("Link accounts")}}}
@Composable fun StateScreen(title:String,body:String){Column(Modifier.fillMaxWidth().padding(20.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){Text(title,style=MaterialTheme.typography.titleMedium);Text(body,color=MaterialTheme.colorScheme.onSurfaceVariant)}}
